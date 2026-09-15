#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "thermometer_config.h"

typedef enum {
    APPLICATION_AUTH_SUCCESS,
    APPLICATION_AUTH_REQUIRED,
    APPLICATION_AUTH_FAILED,
    APPLICATION_AUTH_LOCKED,
    APPLICATION_AUTH_INTERNAL_ERROR,
} application_auth_result_t;

typedef struct {
    uint8_t device_id[6];
    uint8_t nonce[THERMOMETER_AUTH_NONCE_SIZE];
    int64_t issued_at_us;
    bool challenge_active;
    bool authenticated;
    bool disconnect_requested;
} application_auth_session_t;

void application_auth_session_start(application_auth_session_t *session,
                                    const uint8_t device_id[6]);
void application_auth_session_end(application_auth_session_t *session);
application_auth_result_t application_auth_begin(
    application_auth_session_t *session);
application_auth_result_t application_auth_prove(
    application_auth_session_t *session, uint32_t boot_id,
    const uint8_t proof[THERMOMETER_AUTH_PROOF_SIZE]);
bool application_auth_is_authenticated(
    const application_auth_session_t *session);
bool application_auth_take_disconnect(application_auth_session_t *session);
