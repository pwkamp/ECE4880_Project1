#include "temperature_sensors.h"

#include <inttypes.h>

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "thermometer_config.h"

enum {
    DS18B20_SKIP_ROM = 0xCC,
    DS18B20_CONVERT_T = 0x44,
    DS18B20_READ_SCRATCHPAD = 0xBE,
};

typedef struct {
    bool connected;
    esp_err_t last_error;
    uint32_t consecutive_failures;
} sensor_health_t;

static const char *TAG = "real_sensors";
static const gpio_num_t SENSOR_GPIOS[THERMOMETER_SENSOR_COUNT] = {
    GPIO_NUM_14,
    GPIO_NUM_27,
};
static portMUX_TYPE s_one_wire_mux = portMUX_INITIALIZER_UNLOCKED;
static sensor_health_t s_sensor_health[THERMOMETER_SENSOR_COUNT];

_Static_assert(THERMOMETER_SENSOR_COUNT == 2,
               "the hardware has exactly two DS18B20 buses");

static void one_wire_drive_low(gpio_num_t gpio)
{
    (void)gpio_set_level(gpio, 0);
}

static void one_wire_release(gpio_num_t gpio)
{
    (void)gpio_set_level(gpio, 1);
}

static bool one_wire_reset(gpio_num_t gpio)
{
    bool present;

    portENTER_CRITICAL(&s_one_wire_mux);
    one_wire_release(gpio);
    esp_rom_delay_us(5);
    if (gpio_get_level(gpio) == 0) {
        /* A bus shorted to ground is not a valid presence pulse. */
        portEXIT_CRITICAL(&s_one_wire_mux);
        return false;
    }

    one_wire_drive_low(gpio);
    esp_rom_delay_us(480);
    one_wire_release(gpio);
    esp_rom_delay_us(70);
    present = gpio_get_level(gpio) == 0;
    esp_rom_delay_us(410);
    portEXIT_CRITICAL(&s_one_wire_mux);
    return present;
}

static void one_wire_write_bit(gpio_num_t gpio, bool bit)
{
    portENTER_CRITICAL(&s_one_wire_mux);
    one_wire_drive_low(gpio);
    if (bit) {
        esp_rom_delay_us(6);
        one_wire_release(gpio);
        esp_rom_delay_us(64);
    } else {
        esp_rom_delay_us(60);
        one_wire_release(gpio);
        esp_rom_delay_us(10);
    }
    portEXIT_CRITICAL(&s_one_wire_mux);
}

static bool one_wire_read_bit(gpio_num_t gpio)
{
    bool bit;

    portENTER_CRITICAL(&s_one_wire_mux);
    one_wire_drive_low(gpio);
    esp_rom_delay_us(3);
    one_wire_release(gpio);
    esp_rom_delay_us(10);
    bit = gpio_get_level(gpio) != 0;
    esp_rom_delay_us(53);
    portEXIT_CRITICAL(&s_one_wire_mux);
    return bit;
}

static void one_wire_write_byte(gpio_num_t gpio, uint8_t value)
{
    for (unsigned int bit = 0; bit < 8U; ++bit) {
        one_wire_write_bit(gpio, (value & 0x01U) != 0U);
        value >>= 1;
    }
}

static uint8_t one_wire_read_byte(gpio_num_t gpio)
{
    uint8_t value = 0U;
    for (unsigned int bit = 0; bit < 8U; ++bit) {
        if (one_wire_read_bit(gpio)) {
            value |= (uint8_t)(1U << bit);
        }
    }
    return value;
}

static uint8_t dallas_crc8(const uint8_t *data, size_t length)
{
    uint8_t crc = 0U;
    while (length-- != 0U) {
        uint8_t byte = *data++;
        for (unsigned int bit = 0; bit < 8U; ++bit) {
            const bool mix = ((crc ^ byte) & 0x01U) != 0U;
            crc >>= 1;
            if (mix) {
                crc ^= 0x8CU;
            }
            byte >>= 1;
        }
    }
    return crc;
}

static esp_err_t start_conversion(gpio_num_t gpio)
{
    if (!one_wire_reset(gpio)) {
        return ESP_ERR_NOT_FOUND;
    }
    one_wire_write_byte(gpio, DS18B20_SKIP_ROM);
    one_wire_write_byte(gpio, DS18B20_CONVERT_T);
    return ESP_OK;
}

static esp_err_t read_temperature(gpio_num_t gpio, int16_t *raw_temperature)
{
    if (!one_wire_reset(gpio)) {
        return ESP_ERR_NOT_FOUND;
    }
    one_wire_write_byte(gpio, DS18B20_SKIP_ROM);
    one_wire_write_byte(gpio, DS18B20_READ_SCRATCHPAD);

    uint8_t scratchpad[9];
    for (size_t index = 0; index < sizeof(scratchpad); ++index) {
        scratchpad[index] = one_wire_read_byte(gpio);
    }
    if (dallas_crc8(scratchpad, 8U) != scratchpad[8]) {
        return ESP_ERR_INVALID_CRC;
    }

    *raw_temperature = (int16_t)((uint16_t)scratchpad[0] |
                                 ((uint16_t)scratchpad[1] << 8));
    return ESP_OK;
}

static void report_sensor_result(size_t sensor_index, esp_err_t error)
{
    sensor_health_t *health = &s_sensor_health[sensor_index];
    const gpio_num_t gpio = SENSOR_GPIOS[sensor_index];

    if (error == ESP_OK) {
        if (!health->connected) {
            ESP_LOGI(TAG, "sensor %u connected on GPIO%d",
                     (unsigned int)(sensor_index + 1U), (int)gpio);
        }
        health->connected = true;
        health->last_error = ESP_OK;
        health->consecutive_failures = 0U;
        return;
    }

    const bool error_changed = error != health->last_error;
    const bool was_connected = health->connected;
    health->connected = false;
    health->last_error = error;
    if (health->consecutive_failures < UINT32_MAX) {
        ++health->consecutive_failures;
    }

    if (!was_connected && !error_changed &&
        health->consecutive_failures != 1U &&
        (health->consecutive_failures % 5U) != 0U) {
        return;
    }

    ESP_LOGW(TAG, "sensor %u on GPIO%d unavailable: %s (failure %" PRIu32 ")",
             (unsigned int)(sensor_index + 1U), (int)gpio,
             error == ESP_ERR_NOT_FOUND ? "no presence pulse"
                                        : esp_err_to_name(error),
             health->consecutive_failures);
}

esp_err_t temperature_sensors_init(void)
{
    const gpio_config_t gpio = {
        .pin_bit_mask = (1ULL << GPIO_NUM_14) | (1ULL << GPIO_NUM_27),
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    const esp_err_t result = gpio_config(&gpio);
    if (result != ESP_OK) {
        return result;
    }

    one_wire_release(GPIO_NUM_14);
    one_wire_release(GPIO_NUM_27);
    ESP_LOGI(TAG, "DS18B20 buses ready: sensor 1=GPIO14, sensor 2=GPIO27");
    return ESP_OK;
}

temperature_sensor_reading_t temperature_sensor_read(size_t sensor_index,
                                                     uint32_t sample_number)
{
    (void)sample_number;
    temperature_sensor_reading_t reading = {0};
    if (sensor_index >= THERMOMETER_SENSOR_COUNT) {
        return reading;
    }

    const TickType_t cycle_started = xTaskGetTickCount();
    const gpio_num_t gpio = SENSOR_GPIOS[sensor_index];
    esp_err_t result = start_conversion(gpio);
    if (result == ESP_OK) {
        /* Conversion happens in the probe while BLE and controls keep running. */
        vTaskDelay(pdMS_TO_TICKS(750));

        int16_t raw_temperature = 0;
        result = read_temperature(gpio, &raw_temperature);
        if (result == ESP_OK) {
            reading.valid = true;
            reading.temperature_centi_c =
                (int16_t)(((int32_t)raw_temperature * 100) / 16);
        }
    }
    report_sensor_result(sensor_index, result);

    /* Missing and healthy probes both retain the one-second sample cadence. */
    TickType_t next_cycle = cycle_started;
    vTaskDelayUntil(&next_cycle, pdMS_TO_TICKS(THERMOMETER_SAMPLE_PERIOD_MS));
    return reading;
}
