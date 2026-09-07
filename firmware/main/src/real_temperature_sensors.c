#include "temperature_sensors.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "thermometer_config.h"

static const char *TAG = "real_sensors";

esp_err_t temperature_sensors_init(void)
{
    /*
     * Hardware integration stub for SWE-EMB-LLR-302..303 (SCRUM-472..473).
     *
     * Initialize the selected buses and both sensor instances here. Keep each
     * sensor independently addressable so one failed probe never blocks the
     * other. No sensor model or electrical interface is fixed by the current
     * requirements, so this stub deliberately avoids inventing one.
     */
    ESP_LOGW(TAG, "real temperature sensor backend is not implemented");
    return ESP_OK;
}

temperature_sensor_reading_t temperature_sensor_read(size_t sensor_index,
                                                     uint32_t sample_number)
{
    (void)sensor_index;
    (void)sample_number;

    vTaskDelay(pdMS_TO_TICKS(THERMOMETER_SAMPLE_PERIOD_MS));

    /*
     * Start/complete the real conversion here and return valid=true only after
     * validating the driver's result. Keep slow bus waits out of ISRs and let
     * the sampling task block while hardware completes the conversion.
     */
    const temperature_sensor_reading_t not_implemented = {0};
    return not_implemented;
}
