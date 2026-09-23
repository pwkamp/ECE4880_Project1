#pragma once

#include "esp_err.h"

/* Starts the active-low Sensor 1/2 buttons on GPIO34/GPIO35. */
esp_err_t local_controls_start(void);
