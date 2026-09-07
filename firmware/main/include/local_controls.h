#pragma once

#include "esp_err.h"

/* Hardware-independent entry point for the future local buttons/backlight input. */
esp_err_t local_controls_start(void);
