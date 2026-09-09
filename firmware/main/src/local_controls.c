#include "local_controls.h"

#include "esp_log.h"

static const char *TAG = "local_controls";

esp_err_t local_controls_start(void)
{
    /*
     * Integration targets: SWE-EMB-LLR-312 and SWE-EMB-LLR-317
     * (SCRUM-482 and SCRUM-487). This stub defines the input boundary; it does
     * not claim that the physical button timing requirements are implemented.
     *
     * Configure debounced button events here. A Sensor N press should call
     * thermometer_toggle_display(N), which deliberately shares the exact same
     * state and display-render path as the remote SET_DISPLAY command. Backlight
     * input should call thermometer_set_backlight() with a normalized value.
     * Keep GPIO ISR work to event signaling; debounce and rendering belong in a
     * normal task context.
     */
    ESP_LOGI(TAG, "local button/backlight inputs are hardware stubs");
    return ESP_OK;
}
