#include "local_display.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "hd44780.h"

#define LCD_COLUMN_COUNT 16U

static const char *TAG = "real_display";
static hd44780_t s_lcd;
static bool s_initialized;

static esp_err_t write_line(uint8_t row, const char *text)
{
    char line[LCD_COLUMN_COUNT + 1U];
    size_t column = 0U;
    while (column < LCD_COLUMN_COUNT && text[column] != '\0') {
        line[column] = text[column];
        ++column;
    }
    while (column < LCD_COLUMN_COUNT) {
        line[column++] = ' ';
    }
    line[LCD_COLUMN_COUNT] = '\0';

    esp_err_t result = hd44780_gotoxy(&s_lcd, 0U, row);
    if (result == ESP_OK) {
        result = hd44780_puts(&s_lcd, line);
    }
    if (result != ESP_OK) {
        ESP_LOGW(TAG, "LCD row %u write failed: %s", (unsigned int)row,
                 esp_err_to_name(result));
    }
    return result;
}

static void format_sensor_line(char *line, size_t line_size,
                               size_t sensor_index,
                               const thermometer_sensor_snapshot_t *sensor)
{
    const unsigned int sensor_number = (unsigned int)(sensor_index + 1U);
    if (sensor->data_status != THERMOMETER_DATA_VALID) {
        (void)snprintf(line, line_size, "S%u: DISCONNECTED", sensor_number);
        return;
    }
    if (!sensor->display_enabled) {
        (void)snprintf(line, line_size, "Sensor %u: OFF", sensor_number);
        return;
    }

    const int32_t temperature = sensor->temperature_centi_c;
    const uint32_t magnitude =
        (uint32_t)(temperature < 0 ? -temperature : temperature);
    (void)snprintf(line, line_size, "S%u:%s%" PRIu32 ".%02" PRIu32 "C  ON",
                   sensor_number, temperature < 0 ? "-" : "",
                   magnitude / 100U, magnitude % 100U);
}

esp_err_t local_display_init(void)
{
    memset(&s_lcd, 0, sizeof(s_lcd));
    s_lcd.write_cb = NULL;
    s_lcd.pins.rs = GPIO_NUM_16;
    s_lcd.pins.e = GPIO_NUM_17;
    s_lcd.pins.d4 = GPIO_NUM_18;
    s_lcd.pins.d5 = GPIO_NUM_19;
    s_lcd.pins.d6 = GPIO_NUM_21;
    s_lcd.pins.d7 = GPIO_NUM_23;
    s_lcd.pins.bl = HD44780_NOT_USED;
    s_lcd.font = HD44780_FONT_5X8;
    s_lcd.lines = 2U;
    s_lcd.backlight = false;

    esp_err_t result = hd44780_init(&s_lcd);
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "LCD initialization failed: %s", esp_err_to_name(result));
        return result;
    }
    result = hd44780_control(&s_lcd, true, false, false);
    if (result == ESP_OK) {
        result = hd44780_clear(&s_lcd);
    }
    if (result == ESP_OK) {
        result = write_line(0U, "Dual Thermometer");
    }
    if (result == ESP_OK) {
        result = write_line(1U, "Starting sensors");
    }
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "LCD startup write failed: %s", esp_err_to_name(result));
        return result;
    }

    s_initialized = true;
    ESP_LOGI(TAG,
             "LCD ready: RS=GPIO16 E=GPIO17 D4-D7=GPIO18/19/21/23");
    return ESP_OK;
}

void local_display_render(const thermometer_current_snapshot_t *snapshot)
{
    if (!s_initialized || snapshot == NULL) {
        return;
    }

    char line[LCD_COLUMN_COUNT + 1U];
    for (size_t sensor_index = 0; sensor_index < THERMOMETER_SENSOR_COUNT;
         ++sensor_index) {
        format_sensor_line(line, sizeof(line), sensor_index,
                           &snapshot->sensors[sensor_index]);
        (void)write_line((uint8_t)sensor_index, line);
    }
}

esp_err_t local_display_set_backlight(uint8_t brightness_percent)
{
    if (brightness_percent > 100U) {
        return ESP_ERR_INVALID_ARG;
    }

    /* This board powers the LCD backlight directly; there is no control pin. */
    return ESP_OK;
}
