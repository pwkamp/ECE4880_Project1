#include "ble_server.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "local_controls.h"
#include "local_display.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
#include "temperature_sensors.h"
#include "thermometer.h"

static const char *TAG = "main";

static void initialize_nonvolatile_storage(void)
{
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES ||
        result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        result = nvs_flash_init();
    }
    ESP_ERROR_CHECK(result);
}

static void enable_automatic_power_saving(void)
{
#if CONFIG_PM_ENABLE
    const esp_pm_config_t power_config = {
        .max_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ,
        .min_freq_mhz = CONFIG_XTAL_FREQ,
        /* Original ESP32 + main-XTAL BLE clock supports modem sleep and DFS,
         * but not BLE operation during automatic light sleep. */
        .light_sleep_enable = false,
    };
    ESP_ERROR_CHECK(esp_pm_configure(&power_config));
#endif
}

void app_main(void)
{
    /* Requirement: SWE-EMB-LLR-300 (SCRUM-470). */
    initialize_nonvolatile_storage();
    enable_automatic_power_saving();

    ESP_ERROR_CHECK(temperature_sensors_init());

    /* The LCD is an optional local interface. A disconnected, miswired, or
     * failed display must never reset the ESP32 before BLE starts. Rendering
     * remains disabled when initialization fails. */
    const esp_err_t display_result = local_display_init();
    if (display_result != ESP_OK) {
        ESP_LOGE(TAG, "LCD unavailable; continuing without local display: %s",
                 esp_err_to_name(display_result));
    }
    ESP_ERROR_CHECK(thermometer_start());

    if (display_result == ESP_OK) {
        const esp_err_t backlight_result = thermometer_set_backlight(
            THERMOMETER_DEFAULT_BACKLIGHT_PERCENT);
        if (backlight_result != ESP_OK) {
            ESP_LOGW(TAG, "LCD backlight setup failed: %s",
                     esp_err_to_name(backlight_result));
        }
    }

    const esp_err_t controls_result = local_controls_start();
    if (controls_result != ESP_OK) {
        ESP_LOGE(TAG, "local buttons unavailable; continuing: %s",
                 esp_err_to_name(controls_result));
    }
    ESP_ERROR_CHECK(ble_server_start());
}
