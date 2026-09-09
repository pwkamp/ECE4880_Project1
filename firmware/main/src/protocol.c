#include "protocol.h"

#include <stdbool.h>
#include <string.h>

#include "application_auth.h"
#include "thermometer.h"

void protocol_session_start(protocol_session_t *session,
                            const uint8_t device_id[6])
{
    if (session == NULL) {
        return;
    }
    memset(session, 0, sizeof(*session));
    application_auth_session_start(&session->authentication, device_id);
}

void protocol_session_end(protocol_session_t *session)
{
    if (session != NULL) {
        application_auth_session_end(&session->authentication);
        memset(session, 0, sizeof(*session));
    }
}

bool protocol_session_take_bond_reset(protocol_session_t *session)
{
    if (session == NULL || !session->bond_reset_requested) {
        return false;
    }
    session->bond_reset_requested = false;
    return true;
}

bool protocol_session_take_disconnect(protocol_session_t *session)
{
    return session != NULL &&
           application_auth_take_disconnect(&session->authentication);
}

static uint16_t read_u16(const uint8_t *bytes)
{
    return (uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8U);
}

static uint32_t read_u32(const uint8_t *bytes)
{
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8U) |
           ((uint32_t)bytes[2] << 16U) | ((uint32_t)bytes[3] << 24U);
}

static void write_u16(uint8_t *bytes, uint16_t value)
{
    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8U);
}

static void write_i16(uint8_t *bytes, int16_t value)
{
    write_u16(bytes, (uint16_t)value);
}

static void write_u32(uint8_t *bytes, uint32_t value)
{
    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8U);
    bytes[2] = (uint8_t)(value >> 16U);
    bytes[3] = (uint8_t)(value >> 24U);
}

static size_t finish_response(uint8_t *response, uint8_t opcode,
                              uint16_t request_id, protocol_status_t status,
                              size_t payload_length)
{
    response[PROTOCOL_HEADER_VERSION_OFFSET] = THERMOMETER_PROTOCOL_VERSION;
    response[PROTOCOL_HEADER_OPCODE_OFFSET] = opcode;
    write_u16(response + PROTOCOL_HEADER_REQUEST_ID_OFFSET, request_id);
    write_u16(response + PROTOCOL_HEADER_PAYLOAD_LENGTH_OFFSET,
              (uint16_t)payload_length);
    response[PROTOCOL_HEADER_STATUS_OFFSET] = (uint8_t)status;
    response[PROTOCOL_HEADER_FLAGS_OFFSET] = PROTOCOL_RESPONSE_FLAG;
    return PROTOCOL_HEADER_SIZE + payload_length;
}

static size_t handle_auth_begin(protocol_session_t *session, uint8_t opcode,
                                uint16_t request_id, uint8_t *response,
                                size_t response_capacity)
{
    const application_auth_result_t result =
        application_auth_begin(&session->authentication);
    if (result == APPLICATION_AUTH_LOCKED) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_LOCKED, 0U);
    }
    if (result != APPLICATION_AUTH_SUCCESS) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }
    if (response_capacity <
        PROTOCOL_HEADER_SIZE + PROTOCOL_AUTH_BEGIN_RESPONSE_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }

    thermometer_current_snapshot_t snapshot;
    thermometer_get_current(&snapshot);
    uint8_t *payload = response + PROTOCOL_HEADER_SIZE;
    memcpy(payload + PROTOCOL_AUTH_BEGIN_RESPONSE_DEVICE_ID_OFFSET,
           session->authentication.device_id,
           sizeof(session->authentication.device_id));
    write_u32(payload + PROTOCOL_AUTH_BEGIN_RESPONSE_BOOT_ID_OFFSET,
              snapshot.boot_id);
    memcpy(payload + PROTOCOL_AUTH_BEGIN_RESPONSE_NONCE_OFFSET,
           session->authentication.nonce,
           sizeof(session->authentication.nonce));
    return finish_response(response, opcode, request_id,
                           PROTOCOL_STATUS_SUCCESS,
                           PROTOCOL_AUTH_BEGIN_RESPONSE_SIZE);
}

static size_t handle_auth_prove(protocol_session_t *session,
                                const uint8_t *payload,
                                size_t payload_length, uint8_t opcode,
                                uint16_t request_id, uint8_t *response)
{
    if (payload_length != PROTOCOL_AUTH_PROVE_REQUEST_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_REQUIRED, 0U);
    }

    thermometer_current_snapshot_t snapshot;
    thermometer_get_current(&snapshot);
    const uint8_t *received =
        payload + PROTOCOL_AUTH_PROVE_REQUEST_PROOF_OFFSET;
    const application_auth_result_t result = application_auth_prove(
        &session->authentication, snapshot.boot_id, received);
    if (result == APPLICATION_AUTH_LOCKED) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_LOCKED, 0U);
    }
    if (result == APPLICATION_AUTH_FAILED) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_FAILED, 0U);
    }
    if (result == APPLICATION_AUTH_REQUIRED) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_REQUIRED, 0U);
    }
    if (result != APPLICATION_AUTH_SUCCESS) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }
    return finish_response(response, opcode, request_id,
                           PROTOCOL_STATUS_SUCCESS, 0U);
}

static void encode_sensor_snapshot(
    uint8_t *payload, const thermometer_sensor_snapshot_t *sensor,
    size_t temperature_offset, size_t state_offset, size_t enabled_offset)
{
    write_i16(payload + temperature_offset, sensor->temperature_centi_c);
    payload[state_offset] = (uint8_t)thermometer_visible_state(sensor);
    payload[enabled_offset] = sensor->display_enabled ? 1U : 0U;
}

static size_t handle_get_current(uint8_t opcode, uint16_t request_id,
                                 uint8_t *response, size_t response_capacity)
{
    if (response_capacity <
        PROTOCOL_HEADER_SIZE + PROTOCOL_CURRENT_RESPONSE_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }

    thermometer_current_snapshot_t snapshot;
    thermometer_get_current(&snapshot);
    uint8_t *payload = response + PROTOCOL_HEADER_SIZE;
    write_u32(payload + PROTOCOL_CURRENT_RESPONSE_BOOT_ID_OFFSET,
              snapshot.boot_id);
    write_u32(payload + PROTOCOL_CURRENT_RESPONSE_NEWEST_SEQUENCE_OFFSET,
              snapshot.newest_sequence);
    encode_sensor_snapshot(
        payload, &snapshot.sensors[0],
        PROTOCOL_CURRENT_RESPONSE_SENSOR_1_TEMPERATURE_CENTI_C_OFFSET,
        PROTOCOL_CURRENT_RESPONSE_SENSOR_1_VISIBLE_STATE_OFFSET,
        PROTOCOL_CURRENT_RESPONSE_SENSOR_1_DISPLAY_ENABLED_OFFSET);
    encode_sensor_snapshot(
        payload, &snapshot.sensors[1],
        PROTOCOL_CURRENT_RESPONSE_SENSOR_2_TEMPERATURE_CENTI_C_OFFSET,
        PROTOCOL_CURRENT_RESPONSE_SENSOR_2_VISIBLE_STATE_OFFSET,
        PROTOCOL_CURRENT_RESPONSE_SENSOR_2_DISPLAY_ENABLED_OFFSET);
    write_i16(
        payload + PROTOCOL_CURRENT_RESPONSE_AVERAGE_TEMPERATURE_CENTI_C_OFFSET,
        snapshot.average_centi_c);
    payload[PROTOCOL_CURRENT_RESPONSE_AVERAGE_VALID_OFFSET] =
        snapshot.average_valid ? 1U : 0U;
    payload[PROTOCOL_CURRENT_RESPONSE_RESERVED_OFFSET] = 0U;

    return finish_response(response, opcode, request_id,
                           PROTOCOL_STATUS_SUCCESS,
                           PROTOCOL_CURRENT_RESPONSE_SIZE);
}

static size_t handle_set_display(const uint8_t *payload,
                                 size_t payload_length, uint8_t opcode,
                                 uint16_t request_id, uint8_t *response,
                                 size_t response_capacity)
{
    if (payload_length != PROTOCOL_SET_DISPLAY_REQUEST_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }

    const uint8_t sensor_id =
        payload[PROTOCOL_SET_DISPLAY_REQUEST_SENSOR_ID_OFFSET];
    const uint8_t enabled =
        payload[PROTOCOL_SET_DISPLAY_REQUEST_ENABLED_OFFSET];
    if (sensor_id == 0U || sensor_id > THERMOMETER_SENSOR_COUNT) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_SENSOR, 0U);
    }
    if (enabled > 1U) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }
    if (response_capacity <
        PROTOCOL_HEADER_SIZE + PROTOCOL_SET_DISPLAY_RESPONSE_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }

    thermometer_visible_state_t visible_state =
        THERMOMETER_VISIBLE_DISCONNECTED;
    bool display_enabled = false;
    const bool sensor_available = thermometer_set_display(
        sensor_id, enabled != 0U, &visible_state, &display_enabled);

    uint8_t *result = response + PROTOCOL_HEADER_SIZE;
    result[PROTOCOL_SET_DISPLAY_RESPONSE_SENSOR_ID_OFFSET] = sensor_id;
    result[PROTOCOL_SET_DISPLAY_RESPONSE_VISIBLE_STATE_OFFSET] =
        (uint8_t)visible_state;
    result[PROTOCOL_SET_DISPLAY_RESPONSE_ENABLED_OFFSET] =
        display_enabled ? 1U : 0U;
    return finish_response(response, opcode, request_id,
                           sensor_available ? PROTOCOL_STATUS_SUCCESS
                                            : PROTOCOL_STATUS_NOT_AVAILABLE,
                           PROTOCOL_SET_DISPLAY_RESPONSE_SIZE);
}

static size_t handle_get_history_meta(uint8_t opcode, uint16_t request_id,
                                      uint8_t *response,
                                      size_t response_capacity)
{
    if (response_capacity <
        PROTOCOL_HEADER_SIZE + PROTOCOL_HISTORY_META_RESPONSE_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }

    thermometer_history_meta_t meta;
    thermometer_get_history_meta(&meta);
    uint8_t *payload = response + PROTOCOL_HEADER_SIZE;
    write_u32(payload + PROTOCOL_HISTORY_META_RESPONSE_BOOT_ID_OFFSET,
              meta.boot_id);
    write_u32(
        payload + PROTOCOL_HISTORY_META_RESPONSE_NEWEST_SEQUENCE_OFFSET,
        meta.newest_sequence);
    write_u16(payload + PROTOCOL_HISTORY_META_RESPONSE_SENSOR_1_COUNT_OFFSET,
              meta.counts[0]);
    write_u16(payload + PROTOCOL_HISTORY_META_RESPONSE_SENSOR_2_COUNT_OFFSET,
              meta.counts[1]);
    write_u32(
        payload +
            PROTOCOL_HISTORY_META_RESPONSE_SENSOR_1_OLDEST_SEQUENCE_OFFSET,
        meta.oldest_sequences[0]);
    write_u32(
        payload +
            PROTOCOL_HISTORY_META_RESPONSE_SENSOR_2_OLDEST_SEQUENCE_OFFSET,
        meta.oldest_sequences[1]);

    return finish_response(response, opcode, request_id,
                           PROTOCOL_STATUS_SUCCESS,
                           PROTOCOL_HISTORY_META_RESPONSE_SIZE);
}

static size_t handle_get_history_chunk(const uint8_t *payload,
                                       size_t payload_length, uint8_t opcode,
                                       uint16_t request_id, uint8_t *response,
                                       size_t response_capacity)
{
    if (payload_length != PROTOCOL_HISTORY_CHUNK_REQUEST_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }

    const uint8_t sensor_id =
        payload[PROTOCOL_HISTORY_CHUNK_REQUEST_SENSOR_ID_OFFSET];
    const uint32_t start_sequence = read_u32(
        payload + PROTOCOL_HISTORY_CHUNK_REQUEST_START_SEQUENCE_OFFSET);
    size_t requested_count =
        payload[PROTOCOL_HISTORY_CHUNK_REQUEST_RECORD_COUNT_OFFSET];
    if (sensor_id == 0U || sensor_id > THERMOMETER_SENSOR_COUNT) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_SENSOR, 0U);
    }
    if (requested_count == 0U) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }

    if (requested_count > PROTOCOL_MAX_HISTORY_RECORDS) {
        requested_count = PROTOCOL_MAX_HISTORY_RECORDS;
    }
    const size_t packet_overhead =
        PROTOCOL_HEADER_SIZE + PROTOCOL_HISTORY_CHUNK_PREFIX_SIZE;
    const size_t records_that_fit = response_capacity > packet_overhead
                                        ? (response_capacity - packet_overhead) /
                                              PROTOCOL_HISTORY_RECORD_SIZE
                                        : 0U;
    if (requested_count > records_that_fit) {
        requested_count = records_that_fit;
    }
    if (requested_count == 0U) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INTERNAL_ERROR, 0U);
    }

    thermometer_history_record_t records[PROTOCOL_MAX_HISTORY_RECORDS];
    size_t copied_count = 0U;
    if (!thermometer_copy_history(sensor_id, start_sequence, requested_count,
                                  records, &copied_count)) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_NOT_AVAILABLE, 0U);
    }

    uint8_t *result = response + PROTOCOL_HEADER_SIZE;
    result[PROTOCOL_HISTORY_CHUNK_PREFIX_SENSOR_ID_OFFSET] = sensor_id;
    write_u32(result + PROTOCOL_HISTORY_CHUNK_PREFIX_START_SEQUENCE_OFFSET,
              start_sequence);
    result[PROTOCOL_HISTORY_CHUNK_PREFIX_RECORD_COUNT_OFFSET] =
        (uint8_t)copied_count;
    result[PROTOCOL_HISTORY_CHUNK_PREFIX_RECORD_SIZE_OFFSET] =
        PROTOCOL_HISTORY_RECORD_SIZE;

    uint8_t *encoded_records = result + PROTOCOL_HISTORY_CHUNK_PREFIX_SIZE;
    for (size_t record_index = 0; record_index < copied_count;
         ++record_index) {
        uint8_t *encoded_record =
            encoded_records + record_index * PROTOCOL_HISTORY_RECORD_SIZE;
        write_u32(encoded_record + PROTOCOL_HISTORY_RECORD_SEQUENCE_OFFSET,
                  records[record_index].sequence);
        write_i16(encoded_record +
                      PROTOCOL_HISTORY_RECORD_TEMPERATURE_CENTI_C_OFFSET,
                  records[record_index].temperature_centi_c);
        encoded_record[PROTOCOL_HISTORY_RECORD_DATA_STATUS_OFFSET] =
            (uint8_t)records[record_index].data_status;
    }

    const size_t response_payload_length =
        PROTOCOL_HISTORY_CHUNK_PREFIX_SIZE +
        copied_count * PROTOCOL_HISTORY_RECORD_SIZE;
    return finish_response(response, opcode, request_id,
                           PROTOCOL_STATUS_SUCCESS, response_payload_length);
}

size_t protocol_process_request(protocol_session_t *session,
                                const uint8_t *request, size_t request_length,
                                uint8_t *response, size_t response_capacity)
{
    if (session == NULL || response == NULL ||
        response_capacity < PROTOCOL_HEADER_SIZE) {
        return 0U;
    }

    memset(response, 0, response_capacity);
    const uint8_t opcode =
        request != NULL && request_length > PROTOCOL_HEADER_OPCODE_OFFSET
            ? request[PROTOCOL_HEADER_OPCODE_OFFSET]
            : 0U;
    const uint16_t request_id =
        request != NULL &&
                request_length >=
                    PROTOCOL_HEADER_REQUEST_ID_OFFSET + sizeof(uint16_t)
            ? read_u16(request + PROTOCOL_HEADER_REQUEST_ID_OFFSET)
            : 0U;
    if (request == NULL || request_length < PROTOCOL_HEADER_SIZE) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }
    if (request[PROTOCOL_HEADER_VERSION_OFFSET] !=
        THERMOMETER_PROTOCOL_VERSION) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_UNSUPPORTED_VERSION, 0U);
    }

    const size_t payload_length = request_length - PROTOCOL_HEADER_SIZE;
    const uint16_t declared_payload_length =
        read_u16(request + PROTOCOL_HEADER_PAYLOAD_LENGTH_OFFSET);
    if (request[PROTOCOL_HEADER_STATUS_OFFSET] != 0U ||
        request[PROTOCOL_HEADER_FLAGS_OFFSET] != 0U ||
        declared_payload_length != payload_length) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_VALUE, 0U);
    }

    const uint8_t *payload = request + PROTOCOL_HEADER_SIZE;
    /*
     * Requirement: INT-LLR-401 (SCRUM-508). Requests are writes and
     * responses are reads; the peripheral never initiates an application
     * message or notification.
     */
    switch (opcode) {
    case PROTOCOL_OP_AUTH_BEGIN:
        if (payload_length != 0U) {
            return finish_response(response, opcode, request_id,
                                   PROTOCOL_STATUS_INVALID_VALUE, 0U);
        }
        return handle_auth_begin(session, opcode, request_id, response,
                                 response_capacity);
    case PROTOCOL_OP_AUTH_PROVE:
        return handle_auth_prove(session, payload, payload_length, opcode,
                                 request_id, response);
    default:
        break;
    }

    if (!application_auth_is_authenticated(&session->authentication)) {
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_AUTHENTICATION_REQUIRED, 0U);
    }

    switch (opcode) {
    case PROTOCOL_OP_GET_CURRENT:
        if (payload_length != 0U) {
            return finish_response(response, opcode, request_id,
                                   PROTOCOL_STATUS_INVALID_VALUE, 0U);
        }
        return handle_get_current(opcode, request_id, response,
                                  response_capacity);
    case PROTOCOL_OP_SET_DISPLAY:
        return handle_set_display(payload, payload_length, opcode, request_id,
                                  response, response_capacity);
    case PROTOCOL_OP_GET_HISTORY_META:
        if (payload_length != 0U) {
            return finish_response(response, opcode, request_id,
                                   PROTOCOL_STATUS_INVALID_VALUE, 0U);
        }
        return handle_get_history_meta(opcode, request_id, response,
                                       response_capacity);
    case PROTOCOL_OP_GET_HISTORY_CHUNK:
        return handle_get_history_chunk(payload, payload_length, opcode,
                                        request_id, response,
                                        response_capacity);
    case PROTOCOL_OP_RESET_BOND:
        if (payload_length != 0U) {
            return finish_response(response, opcode, request_id,
                                   PROTOCOL_STATUS_INVALID_VALUE, 0U);
        }
        session->bond_reset_requested = true;
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_SUCCESS, 0U);
    default:
        return finish_response(response, opcode, request_id,
                               PROTOCOL_STATUS_INVALID_COMMAND, 0U);
    }
}
