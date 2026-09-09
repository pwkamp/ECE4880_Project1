#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "thermometer.h"

/* Exactly one backend implements this interface, selected in menuconfig. */
esp_err_t local_display_init(void);
void local_display_render(const thermometer_current_snapshot_t *snapshot);
esp_err_t local_display_set_backlight(uint8_t brightness_percent);
