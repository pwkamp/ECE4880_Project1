#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

typedef struct {
    bool valid;
    int16_t temperature_centi_c;
} temperature_sensor_reading_t;

/* Exactly one physical/test backend implements this interface. */
esp_err_t temperature_sensors_init(void);
/* Block until this sensor's next conversion completes. */
temperature_sensor_reading_t temperature_sensor_read(size_t sensor_index,
                                                     uint32_t sample_number);
