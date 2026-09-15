#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "thermometer_config.h"

typedef enum {
    THERMOMETER_DATA_VALID = PROTOCOL_DATA_STATUS_VALUE_VALID,
    THERMOMETER_DATA_DISCONNECTED = PROTOCOL_DATA_STATUS_VALUE_DISCONNECTED,
} thermometer_data_status_t;

typedef enum {
    THERMOMETER_VISIBLE_OFF = PROTOCOL_VISIBLE_STATE_VALUE_OFF,
    THERMOMETER_VISIBLE_ON = PROTOCOL_VISIBLE_STATE_VALUE_ON,
    THERMOMETER_VISIBLE_DISCONNECTED = PROTOCOL_VISIBLE_STATE_VALUE_DISCONNECTED,
} thermometer_visible_state_t;

typedef struct {
    int16_t temperature_centi_c;
    thermometer_data_status_t data_status;
    bool display_enabled;
    uint32_t sequence;
} thermometer_sensor_snapshot_t;

typedef struct {
    uint32_t boot_id;
    uint32_t newest_sequence;
    thermometer_sensor_snapshot_t sensors[THERMOMETER_SENSOR_COUNT];
    int16_t average_centi_c;
    bool average_valid;
} thermometer_current_snapshot_t;

typedef struct {
    uint32_t sequence;
    int16_t temperature_centi_c;
    thermometer_data_status_t data_status;
} thermometer_history_record_t;

typedef struct {
    uint32_t boot_id;
    uint32_t newest_sequence;
    uint16_t counts[THERMOMETER_SENSOR_COUNT];
    uint32_t oldest_sequences[THERMOMETER_SENSOR_COUNT];
} thermometer_history_meta_t;

esp_err_t thermometer_start(void);
void thermometer_get_current(thermometer_current_snapshot_t *snapshot);
void thermometer_get_history_meta(thermometer_history_meta_t *meta);

thermometer_visible_state_t thermometer_visible_state(
    const thermometer_sensor_snapshot_t *sensor);

bool thermometer_set_display(uint8_t sensor_id, bool enabled,
                             thermometer_visible_state_t *resulting_state,
                             bool *resulting_enabled);
bool thermometer_toggle_display(uint8_t sensor_id);
esp_err_t thermometer_set_backlight(uint8_t brightness_percent);

bool thermometer_copy_history(uint8_t sensor_id, uint32_t start_sequence,
                              size_t requested_count,
                              thermometer_history_record_t *records,
                              size_t *copied_count);
