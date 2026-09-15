#include "ble_server.h"

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "esp_mac.h"
#include "host/ble_att.h"
#include "host/ble_gatt.h"
#include "host/ble_hs.h"
#include "host/ble_hs_mbuf.h"
#include "host/ble_sm.h"
#include "host/ble_uuid.h"
#include "host/util/util.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "os/os_mbuf.h"
#include "protocol.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

static const char *TAG = "thermometer_ble";

static ble_uuid_any_t s_service_uuid;
static ble_uuid_any_t s_request_uuid;
static ble_uuid_any_t s_response_uuid;
static uint8_t s_own_address_type;
static uint8_t s_response[PROTOCOL_MAX_PACKET_SIZE];
static size_t s_response_length;
static uint8_t s_device_id[6];
static char s_device_name[25];
static protocol_session_t s_protocol_session;
static bool s_clear_bond_on_disconnect;
static ble_addr_t s_bond_to_clear;

typedef enum {
    GATT_REQUEST_CHARACTERISTIC,
    GATT_RESPONSE_CHARACTERISTIC,
} gatt_characteristic_role_t;

static const gatt_characteristic_role_t REQUEST_ROLE =
    GATT_REQUEST_CHARACTERISTIC;
static const gatt_characteristic_role_t RESPONSE_ROLE =
    GATT_RESPONSE_CHARACTERISTIC;

void ble_store_config_init(void);

static int handle_characteristic_access(
    uint16_t connection_handle, uint16_t attribute_handle,
    struct ble_gatt_access_ctxt *context, void *argument);

static struct ble_gatt_chr_def s_characteristics[] = {
    {
        .access_cb = handle_characteristic_access,
        .arg = (void *)&REQUEST_ROLE,
        .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_ENC |
                 BLE_GATT_CHR_F_WRITE_AUTHEN,
    },
    {
        .access_cb = handle_characteristic_access,
        .arg = (void *)&RESPONSE_ROLE,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_READ_ENC |
                 BLE_GATT_CHR_F_READ_AUTHEN,
    },
    {0},
};

static struct ble_gatt_svc_def s_services[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .characteristics = s_characteristics,
    },
    {0},
};

static int handle_characteristic_access(
    uint16_t connection_handle, uint16_t attribute_handle,
    struct ble_gatt_access_ctxt *context, void *argument)
{
    (void)attribute_handle;
    const gatt_characteristic_role_t characteristic =
        *(const gatt_characteristic_role_t *)argument;

    if (characteristic == GATT_REQUEST_CHARACTERISTIC &&
        context->op == BLE_GATT_ACCESS_OP_WRITE_CHR) {
        const uint16_t request_length = OS_MBUF_PKTLEN(context->om);
        if (request_length < PROTOCOL_HEADER_SIZE ||
            request_length > PROTOCOL_MAX_PACKET_SIZE) {
            return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
        }

        uint8_t request[PROTOCOL_MAX_PACKET_SIZE];
        const int rc = ble_hs_mbuf_to_flat(context->om, request,
                                           sizeof(request), NULL);
        if (rc != 0) {
            return BLE_ATT_ERR_UNLIKELY;
        }
        s_response_length = protocol_process_request(
            &s_protocol_session, request, request_length, s_response,
            sizeof(s_response));
        if (protocol_session_take_bond_reset(&s_protocol_session)) {
            struct ble_gap_conn_desc description;
            if (ble_gap_conn_find(connection_handle, &description) == 0) {
                s_bond_to_clear = description.peer_id_addr;
                s_clear_bond_on_disconnect = true;
                ESP_LOGI(TAG, "authorized bond reset scheduled");
            }
        }
        return s_response_length > 0U ? 0 : BLE_ATT_ERR_UNLIKELY;
    }

    if (characteristic == GATT_RESPONSE_CHARACTERISTIC &&
        context->op == BLE_GATT_ACCESS_OP_READ_CHR) {
        const int rc = os_mbuf_append(context->om, s_response, s_response_length);
        if (rc == 0 &&
            protocol_session_take_disconnect(&s_protocol_session)) {
            (void)ble_gap_terminate(connection_handle,
                                    BLE_ERR_REM_USER_CONN_TERM);
        }
        return rc == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }

    return BLE_ATT_ERR_UNLIKELY;
}

static void start_advertising(void);

static void request_power_saving_connection_interval(uint16_t connection_handle)
{
    const struct ble_gap_upd_params parameters = {
        .itvl_min = THERMOMETER_BLE_CONN_INTERVAL_MIN_UNITS,
        .itvl_max = THERMOMETER_BLE_CONN_INTERVAL_MAX_UNITS,
        .latency = THERMOMETER_BLE_PERIPHERAL_LATENCY,
        .supervision_timeout = THERMOMETER_BLE_SUPERVISION_TIMEOUT_UNITS,
    };
    const int result = ble_gap_update_params(connection_handle, &parameters);
    if (result != 0) {
        ESP_LOGW(TAG, "could not request preferred connection interval: %d",
                 result);
    }
}

static int handle_gap_event(struct ble_gap_event *event, void *argument)
{
    (void)argument;
    struct ble_gap_conn_desc description;

    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status == 0) {
            ESP_LOGI(TAG, "client connected (handle=%u)",
                     event->connect.conn_handle);
            request_power_saving_connection_interval(
                event->connect.conn_handle);
            protocol_session_start(&s_protocol_session, s_device_id);
        } else {
            ESP_LOGW(TAG, "connection failed (status=%d)",
                     event->connect.status);
            start_advertising();
        }
        return 0;

    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(TAG, "client disconnected (reason=%d)",
                 event->disconnect.reason);
        protocol_session_end(&s_protocol_session);
        if (s_clear_bond_on_disconnect) {
            const int delete_result =
                ble_store_util_delete_peer(&s_bond_to_clear);
            if (delete_result == 0) {
                ESP_LOGI(TAG, "authorized peer bond removed");
            } else {
                ESP_LOGE(TAG, "could not remove authorized peer bond: %d",
                         delete_result);
            }
            s_clear_bond_on_disconnect = false;
            memset(&s_bond_to_clear, 0, sizeof(s_bond_to_clear));
        }
        start_advertising();
        return 0;

    case BLE_GAP_EVENT_ADV_COMPLETE:
        start_advertising();
        return 0;

    case BLE_GAP_EVENT_ENC_CHANGE:
        if (ble_gap_conn_find(event->enc_change.conn_handle, &description) == 0) {
            ESP_LOGI(TAG,
                     "security changed: status=%d encrypted=%u authenticated=%u bonded=%u",
                     event->enc_change.status,
                     description.sec_state.encrypted,
                     description.sec_state.authenticated,
                     description.sec_state.bonded);
        }
        return 0;

    case BLE_GAP_EVENT_CONN_UPDATE:
        if (ble_gap_conn_find(event->conn_update.conn_handle, &description) ==
            0) {
            ESP_LOGI(TAG,
                     "connection parameters: status=%d interval=%u latency=%u timeout=%u",
                     event->conn_update.status, description.conn_itvl,
                     description.conn_latency,
                     description.supervision_timeout);
        }
        return 0;

    case BLE_GAP_EVENT_MTU:
        ESP_LOGI(TAG, "negotiated ATT MTU=%u", event->mtu.value);
        return 0;

    case BLE_GAP_EVENT_REPEAT_PAIRING:
        ESP_LOGW(TAG, "re-pairing rejected; authenticated bond reset required");
        return BLE_GAP_REPEAT_PAIRING_IGNORE;

    case BLE_GAP_EVENT_PASSKEY_ACTION: {
        struct ble_sm_io passkey = {0};
        if (event->passkey.params.action != BLE_SM_IOACT_DISP) {
            ESP_LOGW(TAG, "unsupported passkey action=%u",
                     event->passkey.params.action);
            return 0;
        }
        passkey.action = BLE_SM_IOACT_DISP;
        passkey.passkey = THERMOMETER_BLE_PAIRING_PASSKEY;
        ESP_LOGI(TAG, "authenticated passkey pairing requested");
        return ble_sm_inject_io(event->passkey.conn_handle, &passkey);
    }

    default:
        return 0;
    }
}

static void start_advertising(void)
{
    struct ble_hs_adv_fields fields = {0};
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    /*
     * Keep the unique human-readable name in the primary advertisement.
     * Windows does not always deliver the matching scan response to Bleak,
     * which previously caused otherwise valid devices to appear as Unknown.
     */
    fields.name = (uint8_t *)s_device_name;
    fields.name_len = strlen(s_device_name);
    fields.name_is_complete = 1;

    int rc = ble_gap_adv_set_fields(&fields);
    if (rc != 0) {
        ESP_LOGE(TAG, "failed to set advertising data: %d", rc);
        return;
    }

    struct ble_hs_adv_fields scan_response = {0};
    scan_response.uuids128 = &s_service_uuid.u128;
    scan_response.num_uuids128 = 1;
    scan_response.uuids128_is_complete = 1;
    rc = ble_gap_adv_rsp_set_fields(&scan_response);
    if (rc != 0) {
        ESP_LOGE(TAG, "failed to set scan response: %d", rc);
        return;
    }

    struct ble_gap_adv_params parameters = {0};
    parameters.conn_mode = BLE_GAP_CONN_MODE_UND;
    parameters.disc_mode = BLE_GAP_DISC_MODE_GEN;
    parameters.itvl_min = THERMOMETER_BLE_ADV_INTERVAL_MIN_UNITS;
    parameters.itvl_max = THERMOMETER_BLE_ADV_INTERVAL_MAX_UNITS;
    rc = ble_gap_adv_start(s_own_address_type, NULL, BLE_HS_FOREVER,
                           &parameters, handle_gap_event, NULL);
    if (rc != 0 && rc != BLE_HS_EALREADY) {
        ESP_LOGE(TAG, "failed to start advertising: %d", rc);
    }
}

static void handle_host_reset(int reason)
{
    ESP_LOGE(TAG, "NimBLE host reset (reason=%d)", reason);
}

static void handle_host_sync(void)
{
    int rc = ble_hs_util_ensure_addr(0);
    if (rc == 0) {
        rc = ble_hs_id_infer_auto(0, &s_own_address_type);
    }
    if (rc != 0) {
        ESP_LOGE(TAG, "unable to select BLE identity address: %d", rc);
        return;
    }
    start_advertising();
}

static void run_nimble_host(void *argument)
{
    (void)argument;
    nimble_port_run();
    nimble_port_freertos_deinit();
}

esp_err_t ble_server_start(void)
{
    if (esp_read_mac(s_device_id, ESP_MAC_BT) != ESP_OK) {
        ESP_LOGE(TAG, "could not read the Bluetooth device identity");
        return ESP_FAIL;
    }
    const int name_length = snprintf(
        s_device_name, sizeof(s_device_name), "%s%02X%02X%02X",
        THERMOMETER_BLE_DEVICE_NAME_PREFIX, s_device_id[3], s_device_id[4],
        s_device_id[5]);
    if (name_length <= 0 || (size_t)name_length >= sizeof(s_device_name)) {
        ESP_LOGE(TAG, "generated BLE device name is too long");
        return ESP_ERR_INVALID_SIZE;
    }
    if (ble_uuid_from_str(&s_service_uuid, THERMOMETER_BLE_SERVICE_UUID) != 0 ||
        ble_uuid_from_str(&s_request_uuid, THERMOMETER_BLE_REQUEST_UUID) != 0 ||
        ble_uuid_from_str(&s_response_uuid, THERMOMETER_BLE_RESPONSE_UUID) != 0 ||
        s_service_uuid.u.type != BLE_UUID_TYPE_128 ||
        s_request_uuid.u.type != BLE_UUID_TYPE_128 ||
        s_response_uuid.u.type != BLE_UUID_TYPE_128) {
        ESP_LOGE(TAG, "invalid UUID in the shared protocol configuration");
        return ESP_ERR_INVALID_ARG;
    }

    s_services[0].uuid = &s_service_uuid.u;
    s_characteristics[0].uuid = &s_request_uuid.u;
    s_characteristics[1].uuid = &s_response_uuid.u;

    const esp_err_t init_result = nimble_port_init();
    if (init_result != ESP_OK) {
        return init_result;
    }

    ble_hs_cfg.reset_cb = handle_host_reset;
    ble_hs_cfg.sync_cb = handle_host_sync;
    ble_hs_cfg.store_status_cb = ble_store_util_status_rr;
    /* Requirement: INT-LLR-414 (SCRUM-521). */
    ble_hs_cfg.sm_io_cap = BLE_HS_IO_DISPLAY_ONLY;
    ble_hs_cfg.sm_bonding = 1;
    ble_hs_cfg.sm_mitm = 1;
    ble_hs_cfg.sm_sc = 1;
    ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC |
                                 BLE_SM_PAIR_KEY_DIST_ID;
    ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC |
                                   BLE_SM_PAIR_KEY_DIST_ID;

    if (ble_sm_configure_static_passkey(THERMOMETER_BLE_PAIRING_PASSKEY, true) !=
        0) {
        return ESP_ERR_INVALID_ARG;
    }

    ble_svc_gap_init();
    ble_svc_gatt_init();
    if (ble_svc_gap_device_name_set(s_device_name) != 0 ||
        ble_gatts_count_cfg(s_services) != 0 ||
        ble_gatts_add_svcs(s_services) != 0 ||
        ble_att_set_preferred_mtu(THERMOMETER_BLE_PREFERRED_ATT_MTU) != 0) {
        ESP_LOGE(TAG, "failed to configure GATT server");
        return ESP_FAIL;
    }

    memset(s_response, 0, sizeof(s_response));
    s_response[PROTOCOL_HEADER_VERSION_OFFSET] = THERMOMETER_PROTOCOL_VERSION;
    s_response[PROTOCOL_HEADER_STATUS_OFFSET] = PROTOCOL_STATUS_NOT_AVAILABLE;
    s_response[PROTOCOL_HEADER_FLAGS_OFFSET] = PROTOCOL_RESPONSE_FLAG;
    s_response_length = PROTOCOL_HEADER_SIZE;

    ble_store_config_init();
    nimble_port_freertos_init(run_nimble_host);
    ESP_LOGI(TAG, "service ready; protocol v%u",
             THERMOMETER_PROTOCOL_VERSION);
    return ESP_OK;
}
