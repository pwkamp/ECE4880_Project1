#include "local_display.h"

#include "driver/gpio.h"
#include "sdkconfig.h"

static bool s_initialized;
static bool s_led_on;

static int gpio_level_for(bool on)
{
#if CONFIG_THERMOMETER_LED_ACTIVE_LOW
    return on ? 0 : 1;
#else
    return on ? 1 : 0;
#endif
}

esp_err_t local_display_init(void)
{
    const gpio_config_t gpio = {
        .pin_bit_mask = 1ULL << CONFIG_THERMOMETER_LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t result = gpio_config(&gpio);
    if (result != ESP_OK) {
        return result;
    }

    result = gpio_set_level(CONFIG_THERMOMETER_LED_GPIO, gpio_level_for(false));
    if (result == ESP_OK) {
        s_initialized = true;
        s_led_on = false;
    }
    return result;
}

void local_display_render(const thermometer_current_snapshot_t *snapshot)
{
    if (!s_initialized || snapshot == NULL) {
        return;
    }

    /*
     * The LED is the current LCD simulator. It represents "something is shown"
     * while preserving the two independent logical display flags required by
     * Requirement: SWE-EMB-MLR-305 (SCRUM-461), implemented in the shared
     * thermometer state.
     */
    bool should_be_on = false;
    for (size_t index = 0; index < THERMOMETER_SENSOR_COUNT; ++index) {
        const thermometer_sensor_snapshot_t *sensor = &snapshot->sensors[index];
        should_be_on |= sensor->data_status == THERMOMETER_DATA_VALID &&
                        sensor->display_enabled;
    }

    if (should_be_on != s_led_on) {
        gpio_set_level(CONFIG_THERMOMETER_LED_GPIO, gpio_level_for(should_be_on));
        s_led_on = should_be_on;
    }
}

esp_err_t local_display_set_backlight(uint8_t brightness_percent)
{
    (void)brightness_percent;
    return ESP_OK;
}
