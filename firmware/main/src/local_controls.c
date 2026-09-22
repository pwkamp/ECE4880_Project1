#include "local_controls.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "thermometer.h"

#define BUTTON_TASK_STACK_BYTES 3072U
#define BUTTON_TASK_PRIORITY 5U

typedef struct {
    uint8_t sensor_id;
    gpio_num_t gpio;
    int stable_level;
    int candidate_level;
    TickType_t candidate_since;
} button_state_t;

static const char *TAG = "local_controls";
static const TickType_t BUTTON_POLL_PERIOD = pdMS_TO_TICKS(10);
static const TickType_t BUTTON_DEBOUNCE_TIME = pdMS_TO_TICKS(40);
static const int BUTTON_PRESSED_LEVEL = 0;
static bool s_started;

static bool deadline_reached(TickType_t now, TickType_t deadline)
{
    return (int32_t)(now - deadline) >= 0;
}

static bool poll_button(button_state_t *button, TickType_t now)
{
    const int raw_level = gpio_get_level(button->gpio);
    if (raw_level != button->candidate_level) {
        button->candidate_level = raw_level;
        button->candidate_since = now;
    }

    if (button->candidate_level != button->stable_level &&
        deadline_reached(now,
                         button->candidate_since + BUTTON_DEBOUNCE_TIME)) {
        button->stable_level = button->candidate_level;
        ESP_LOGI(TAG, "sensor %u button GPIO%d %s",
                 (unsigned int)button->sensor_id, (int)button->gpio,
                 button->stable_level == BUTTON_PRESSED_LEVEL ? "pressed"
                                                               : "released");
        return button->stable_level == BUTTON_PRESSED_LEVEL;
    }
    return false;
}

static void button_task(void *unused)
{
    (void)unused;
    TickType_t now = xTaskGetTickCount();
    button_state_t buttons[] = {
        {
            .sensor_id = 1U,
            .gpio = GPIO_NUM_34,
            .stable_level = gpio_get_level(GPIO_NUM_34),
            .candidate_level = gpio_get_level(GPIO_NUM_34),
            .candidate_since = now,
        },
        {
            .sensor_id = 2U,
            .gpio = GPIO_NUM_35,
            .stable_level = gpio_get_level(GPIO_NUM_35),
            .candidate_level = gpio_get_level(GPIO_NUM_35),
            .candidate_since = now,
        },
    };
    TickType_t next_poll = now;

    while (true) {
        now = xTaskGetTickCount();
        for (size_t index = 0; index < sizeof(buttons) / sizeof(buttons[0]);
             ++index) {
            if (poll_button(&buttons[index], now) &&
                !thermometer_toggle_display(buttons[index].sensor_id)) {
                ESP_LOGW(TAG, "sensor %u is disconnected; display unchanged",
                         (unsigned int)buttons[index].sensor_id);
            }
        }
        vTaskDelayUntil(&next_poll, BUTTON_POLL_PERIOD);
    }
}

esp_err_t local_controls_start(void)
{
    if (s_started) {
        return ESP_ERR_INVALID_STATE;
    }

    const gpio_config_t gpio = {
        .pin_bit_mask = (1ULL << GPIO_NUM_34) | (1ULL << GPIO_NUM_35),
        .mode = GPIO_MODE_INPUT,
        /* Input-only GPIO34/35 do not have internal pull resistors. */
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    esp_err_t result = gpio_config(&gpio);
    if (result != ESP_OK) {
        return result;
    }

    if (xTaskCreate(button_task, "local_buttons", BUTTON_TASK_STACK_BYTES, NULL,
                    BUTTON_TASK_PRIORITY, NULL) != pdPASS) {
        return ESP_ERR_NO_MEM;
    }

    s_started = true;
    ESP_LOGI(TAG,
             "buttons ready: sensor 1=GPIO34, sensor 2=GPIO35 (active-low, "
             "40 ms debounce)");
    return ESP_OK;
}
