#include "local_display.h"

#include "esp_log.h"

static const char *TAG = "real_display";

esp_err_t local_display_init(void)
{
    /*
     * Integration targets: SWE-EMB-LLR-318..322 (SCRUM-488..492). This stub
     * defines the hardware boundary; it does not claim that the physical LCD
     * or backlight requirements are implemented.
     *
     * Initialize the selected character-LCD bus, backlight PWM, and display
     * geometry here. The requirements do not yet select I2C, SPI, or parallel
     * wiring, so the interface remains hardware-neutral.
     */
    ESP_LOGW(TAG, "real character LCD backend is not implemented");
    return ESP_OK;
}

void local_display_render(const thermometer_current_snapshot_t *snapshot)
{
    (void)snapshot;
    /*
     * Render from this already-atomic cached snapshot. Show a signed Celsius
     * value when ON, "Sensor N OFF" when OFF, and "DISCONNECTED" for faults.
     * Show the average only when snapshot->average_valid is true.
     */
}

esp_err_t local_display_set_backlight(uint8_t brightness_percent)
{
    if (brightness_percent > 100U) {
        return ESP_ERR_INVALID_ARG;
    }

    /* Map 0..100 percent to the selected PWM/backlight driver here. */
    return ESP_OK;
}
