#include "application_auth.h"

#include <stddef.h>
#include <string.h>

#include "esp_random.h"
#include "esp_timer.h"
#include "psa/crypto.h"

static uint32_t s_failure_count;
static int64_t s_locked_until_us;

static void write_u32(uint8_t *bytes, uint32_t value)
{
    bytes[0] = (uint8_t)value;
    bytes[1] = (uint8_t)(value >> 8U);
    bytes[2] = (uint8_t)(value >> 16U);
    bytes[3] = (uint8_t)(value >> 24U);
}

static bool constant_time_equal(const uint8_t *left, const uint8_t *right,
                                size_t length)
{
    volatile uint8_t difference = 0U;
    for (size_t index = 0; index < length; ++index) {
        difference |= left[index] ^ right[index];
    }
    return difference == 0U;
}

static bool is_locked(int64_t now_us)
{
    if (s_locked_until_us == 0) {
        return false;
    }
    if (now_us < s_locked_until_us) {
        return true;
    }
    s_locked_until_us = 0;
    s_failure_count = 0U;
    return false;
}

static bool calculate_proof(const application_auth_session_t *session,
                            uint32_t boot_id,
                            uint8_t proof[THERMOMETER_AUTH_PROOF_SIZE])
{
    static const uint8_t domain[] = THERMOMETER_AUTH_DOMAIN;
    static const uint8_t passkey[] = THERMOMETER_BLE_PAIRING_PASSKEY_TEXT;
    uint8_t message[(sizeof(domain) - 1U) + 1U + 6U + 4U +
                    THERMOMETER_AUTH_NONCE_SIZE];
    size_t offset = 0U;
    memcpy(message + offset, domain, sizeof(domain) - 1U);
    offset += sizeof(domain) - 1U;
    message[offset++] = THERMOMETER_PROTOCOL_VERSION;
    memcpy(message + offset, session->device_id, sizeof(session->device_id));
    offset += sizeof(session->device_id);
    write_u32(message + offset, boot_id);
    offset += sizeof(boot_id);
    memcpy(message + offset, session->nonce, sizeof(session->nonce));
    offset += sizeof(session->nonce);

    const size_t passkey_length = sizeof(passkey) - 1U;
    if (passkey_length != 6U || psa_crypto_init() != PSA_SUCCESS) {
        return false;
    }
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_SIGN_MESSAGE);
    psa_set_key_algorithm(&attributes, PSA_ALG_HMAC(PSA_ALG_SHA_256));
    psa_set_key_type(&attributes, PSA_KEY_TYPE_HMAC);
    psa_set_key_bits(&attributes, passkey_length * 8U);

    psa_key_id_t key = 0;
    psa_status_t status = psa_import_key(
        &attributes, passkey, passkey_length, &key);
    size_t proof_length = 0U;
    if (status == PSA_SUCCESS) {
        status = psa_mac_compute(
            key, PSA_ALG_HMAC(PSA_ALG_SHA_256), message, offset, proof,
            THERMOMETER_AUTH_PROOF_SIZE, &proof_length);
    }
    if (key != 0) {
        (void)psa_destroy_key(key);
    }
    psa_reset_key_attributes(&attributes);
    return status == PSA_SUCCESS && proof_length == THERMOMETER_AUTH_PROOF_SIZE;
}

void application_auth_session_start(application_auth_session_t *session,
                                    const uint8_t device_id[6])
{
    if (session == NULL || device_id == NULL) {
        return;
    }
    memset(session, 0, sizeof(*session));
    memcpy(session->device_id, device_id, sizeof(session->device_id));
}

void application_auth_session_end(application_auth_session_t *session)
{
    if (session != NULL) {
        memset(session, 0, sizeof(*session));
    }
}

application_auth_result_t application_auth_begin(
    application_auth_session_t *session)
{
    const int64_t now_us = esp_timer_get_time();
    if (session == NULL) {
        return APPLICATION_AUTH_INTERNAL_ERROR;
    }
    if (is_locked(now_us)) {
        return APPLICATION_AUTH_LOCKED;
    }
    esp_fill_random(session->nonce, sizeof(session->nonce));
    session->issued_at_us = now_us;
    session->challenge_active = true;
    session->authenticated = false;
    return APPLICATION_AUTH_SUCCESS;
}

application_auth_result_t application_auth_prove(
    application_auth_session_t *session, uint32_t boot_id,
    const uint8_t proof[THERMOMETER_AUTH_PROOF_SIZE])
{
    const int64_t now_us = esp_timer_get_time();
    if (session == NULL || proof == NULL) {
        return APPLICATION_AUTH_INTERNAL_ERROR;
    }
    if (is_locked(now_us)) {
        session->disconnect_requested = true;
        return APPLICATION_AUTH_LOCKED;
    }
    const int64_t maximum_age_us =
        (int64_t)THERMOMETER_AUTH_CHALLENGE_TIMEOUT_MS * 1000LL;
    if (!session->challenge_active ||
        now_us - session->issued_at_us > maximum_age_us) {
        session->challenge_active = false;
        return APPLICATION_AUTH_REQUIRED;
    }

    uint8_t expected[THERMOMETER_AUTH_PROOF_SIZE];
    const bool valid = calculate_proof(session, boot_id, expected) &&
                       constant_time_equal(expected, proof, sizeof(expected));
    session->challenge_active = false;
    if (!valid) {
        ++s_failure_count;
        session->authenticated = false;
        session->disconnect_requested = true;
        if (s_failure_count >= THERMOMETER_AUTH_MAX_FAILURES) {
            s_locked_until_us =
                now_us + (int64_t)THERMOMETER_AUTH_LOCKOUT_MS * 1000LL;
            return APPLICATION_AUTH_LOCKED;
        }
        return APPLICATION_AUTH_FAILED;
    }

    s_failure_count = 0U;
    s_locked_until_us = 0;
    session->authenticated = true;
    return APPLICATION_AUTH_SUCCESS;
}

bool application_auth_is_authenticated(
    const application_auth_session_t *session)
{
    return session != NULL && session->authenticated;
}

bool application_auth_take_disconnect(application_auth_session_t *session)
{
    if (session == NULL || !session->disconnect_requested) {
        return false;
    }
    session->disconnect_requested = false;
    return true;
}
