#pragma once

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#include "thermometer_config.h"
#include "application_auth.h"

typedef enum {
    PROTOCOL_OP_GET_CURRENT = PROTOCOL_OPCODE_VALUE_GET_CURRENT,
    PROTOCOL_OP_SET_DISPLAY = PROTOCOL_OPCODE_VALUE_SET_DISPLAY,
    PROTOCOL_OP_GET_HISTORY_META = PROTOCOL_OPCODE_VALUE_GET_HISTORY_META,
    PROTOCOL_OP_GET_HISTORY_CHUNK = PROTOCOL_OPCODE_VALUE_GET_HISTORY_CHUNK,
    PROTOCOL_OP_AUTH_BEGIN = PROTOCOL_OPCODE_VALUE_AUTH_BEGIN,
    PROTOCOL_OP_AUTH_PROVE = PROTOCOL_OPCODE_VALUE_AUTH_PROVE,
    PROTOCOL_OP_RESET_BOND = PROTOCOL_OPCODE_VALUE_RESET_BOND,
} protocol_opcode_t;

typedef enum {
    PROTOCOL_STATUS_SUCCESS = PROTOCOL_STATUS_VALUE_SUCCESS,
    PROTOCOL_STATUS_INVALID_COMMAND = PROTOCOL_STATUS_VALUE_INVALID_COMMAND,
    PROTOCOL_STATUS_INVALID_SENSOR = PROTOCOL_STATUS_VALUE_INVALID_SENSOR,
    PROTOCOL_STATUS_INVALID_VALUE = PROTOCOL_STATUS_VALUE_INVALID_VALUE,
    PROTOCOL_STATUS_NOT_AVAILABLE = PROTOCOL_STATUS_VALUE_NOT_AVAILABLE,
    PROTOCOL_STATUS_INTERNAL_ERROR = PROTOCOL_STATUS_VALUE_INTERNAL_ERROR,
    PROTOCOL_STATUS_UNSUPPORTED_VERSION = PROTOCOL_STATUS_VALUE_UNSUPPORTED_VERSION,
    PROTOCOL_STATUS_AUTHENTICATION_REQUIRED = PROTOCOL_STATUS_VALUE_AUTHENTICATION_REQUIRED,
    PROTOCOL_STATUS_AUTHENTICATION_FAILED = PROTOCOL_STATUS_VALUE_AUTHENTICATION_FAILED,
    PROTOCOL_STATUS_AUTHENTICATION_LOCKED = PROTOCOL_STATUS_VALUE_AUTHENTICATION_LOCKED,
} protocol_status_t;

typedef struct {
    application_auth_session_t authentication;
    bool bond_reset_requested;
} protocol_session_t;

void protocol_session_start(protocol_session_t *session,
                            const uint8_t device_id[6]);
void protocol_session_end(protocol_session_t *session);
bool protocol_session_take_bond_reset(protocol_session_t *session);
bool protocol_session_take_disconnect(protocol_session_t *session);

size_t protocol_process_request(protocol_session_t *session,
                                const uint8_t *request, size_t request_length,
                                uint8_t *response, size_t response_capacity);
