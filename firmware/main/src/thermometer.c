#include "thermometer.h"

#include <string.h>

#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "history_buffer.h"
#include "local_display.h"
#include "temperature_sensors.h"

typedef struct {
    thermometer_sensor_snapshot_t latest;
    thermometer_history_buffer_t history;
    uint16_t failed_reads;
    uint16_t successful_reads;
} sensor_runtime_t;

static SemaphoreHandle_t s_state_mutex;
static SemaphoreHandle_t s_display_mutex;
static QueueHandle_t s_sensor_events;
static TaskHandle_t s_state_task;
static TaskHandle_t s_sensor_tasks[THERMOMETER_SENSOR_COUNT];
static sensor_runtime_t s_sensors[THERMOMETER_SENSOR_COUNT];
static uint32_t s_boot_id;
static uint32_t s_latest_sequence;
static bool s_started;

typedef struct {
    size_t sensor_index;
    temperature_sensor_reading_t reading;
} sensor_event_t;

static bool sensor_is_available(const thermometer_sensor_snapshot_t *sensor)
{
    return sensor->data_status == THERMOMETER_DATA_VALID;
}

static bool sensor_is_visible(const thermometer_sensor_snapshot_t *sensor)
{
    return sensor_is_available(sensor) && sensor->display_enabled;
}

thermometer_visible_state_t thermometer_visible_state(
    const thermometer_sensor_snapshot_t *sensor)
{
    if (sensor == NULL || !sensor_is_available(sensor)) {
        return THERMOMETER_VISIBLE_DISCONNECTED;
    }
    return sensor->display_enabled ? THERMOMETER_VISIBLE_ON
                                   : THERMOMETER_VISIBLE_OFF;
}

static void copy_current_snapshot_locked(
    thermometer_current_snapshot_t *snapshot)
{
    snapshot->boot_id = s_boot_id;
    snapshot->newest_sequence = s_latest_sequence;
    for (size_t sensor_index = 0; sensor_index < THERMOMETER_SENSOR_COUNT;
         ++sensor_index) {
        snapshot->sensors[sensor_index] = s_sensors[sensor_index].latest;
    }

    /* Requirement: SWE-EMB-LLR-314 (SCRUM-484). Widen before addition. */
    snapshot->average_valid = sensor_is_visible(&snapshot->sensors[0]) &&
                              sensor_is_visible(&snapshot->sensors[1]);
    const int32_t temperature_sum =
        (int32_t)snapshot->sensors[0].temperature_centi_c +
        (int32_t)snapshot->sensors[1].temperature_centi_c;
    snapshot->average_centi_c = snapshot->average_valid
                                    ? (int16_t)(temperature_sum / 2)
                                    : 0;
}

static void render_current_display(void)
{
    thermometer_current_snapshot_t snapshot;

    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    copy_current_snapshot_locked(&snapshot);
    xSemaphoreGive(s_state_mutex);

    /* Display I/O can be slow, so it never holds the shared state mutex. */
    xSemaphoreTake(s_display_mutex, portMAX_DELAY);
    local_display_render(&snapshot);
    xSemaphoreGive(s_display_mutex);
}

static void apply_sensor_reading(sensor_runtime_t *sensor,
                                 temperature_sensor_reading_t reading)
{
    if (reading.valid) {
        sensor->failed_reads = 0U;
        if (sensor->successful_reads < UINT16_MAX) {
            ++sensor->successful_reads;
        }

        if (sensor->latest.data_status == THERMOMETER_DATA_VALID ||
            sensor->successful_reads >= THERMOMETER_SUCCESSFUL_READ_LIMIT) {
            if (sensor->latest.data_status != THERMOMETER_DATA_VALID) {
                /* Requirement: SWE-EMB-LLR-311 (SCRUM-481). Recovery starts OFF. */
                sensor->latest.display_enabled = false;
            }
            sensor->latest.temperature_centi_c = reading.temperature_centi_c;
            sensor->latest.data_status = THERMOMETER_DATA_VALID;
        }
        return;
    }

    sensor->successful_reads = 0U;
    if (sensor->failed_reads < UINT16_MAX) {
        ++sensor->failed_reads;
    }
    if (sensor->failed_reads >= THERMOMETER_FAILED_READ_LIMIT) {
        /* Requirement: SWE-EMB-LLR-310 (SCRUM-480). Failed reads disconnect. */
        sensor->latest.data_status = THERMOMETER_DATA_DISCONNECTED;
        sensor->latest.display_enabled = false;
    }
}

static void append_history_record(sensor_runtime_t *sensor)
{
    history_buffer_append(
        &sensor->history,
        (thermometer_history_record_t){
            .sequence = s_latest_sequence,
            .temperature_centi_c = sensor->latest.temperature_centi_c,
            .data_status = sensor->latest.data_status,
        });
    sensor->latest.sequence = s_latest_sequence;
}

static void sensor_acquisition_task(void *argument)
{
    const size_t sensor_index = (size_t)(uintptr_t)argument;
    uint32_t sample_number = 0U;

    while (true) {
        sensor_event_t event = {
            .sensor_index = sensor_index,
            .reading = temperature_sensor_read(sensor_index, sample_number),
        };
        ++sample_number;
        (void)xQueueSend(s_sensor_events, &event, portMAX_DELAY);
        /* The backend starts its next conversion on the following call. */
    }
}

static void thermometer_state_task(void *unused)
{
    (void)unused;
    const TickType_t sample_period =
        pdMS_TO_TICKS(THERMOMETER_SAMPLE_PERIOD_MS);
    TickType_t next_snapshot = xTaskGetTickCount() + sample_period;

    while (true) {
        const TickType_t now = xTaskGetTickCount();
        if ((int32_t)(now - next_snapshot) >= 0) {
            xSemaphoreTake(s_state_mutex, portMAX_DELAY);
            ++s_latest_sequence;
            for (size_t sensor_index = 0;
                 sensor_index < THERMOMETER_SENSOR_COUNT; ++sensor_index) {
                /* Requirement: SWE-EMB-LLR-304..307 (SCRUM-474..477). */
                append_history_record(&s_sensors[sensor_index]);
            }
            xSemaphoreGive(s_state_mutex);
            render_current_display();
            next_snapshot += sample_period;
            continue;
        }

        sensor_event_t event;
        if (xQueueReceive(s_sensor_events, &event, next_snapshot - now) ==
            pdTRUE) {
            xSemaphoreTake(s_state_mutex, portMAX_DELAY);
            apply_sensor_reading(&s_sensors[event.sensor_index], event.reading);
            xSemaphoreGive(s_state_mutex);
        }
    }
}

esp_err_t thermometer_start(void)
{
    if (s_started) {
        return ESP_ERR_INVALID_STATE;
    }

    memset(s_sensors, 0, sizeof(s_sensors));
    for (size_t sensor_index = 0; sensor_index < THERMOMETER_SENSOR_COUNT;
         ++sensor_index) {
        history_buffer_init(&s_sensors[sensor_index].history);
        s_sensors[sensor_index].latest.data_status =
            THERMOMETER_DATA_DISCONNECTED;
    }
    s_boot_id = esp_random();

    s_state_mutex = xSemaphoreCreateMutex();
    s_display_mutex = xSemaphoreCreateMutex();
    if (s_state_mutex == NULL || s_display_mutex == NULL) {
        if (s_state_mutex != NULL) {
            vSemaphoreDelete(s_state_mutex);
        }
        if (s_display_mutex != NULL) {
            vSemaphoreDelete(s_display_mutex);
        }
        return ESP_ERR_NO_MEM;
    }

    s_sensor_events = xQueueCreate(THERMOMETER_SENSOR_COUNT * 2U,
                                   sizeof(sensor_event_t));
    if (s_sensor_events == NULL) {
        vSemaphoreDelete(s_display_mutex);
        vSemaphoreDelete(s_state_mutex);
        s_display_mutex = NULL;
        s_state_mutex = NULL;
        return ESP_ERR_NO_MEM;
    }

    BaseType_t task_created = xTaskCreate(
        thermometer_state_task, "thermometer_state",
        THERMOMETER_SAMPLING_TASK_STACK_BYTES, NULL,
        THERMOMETER_SAMPLING_TASK_PRIORITY, &s_state_task);
    if (task_created != pdPASS) {
        vQueueDelete(s_sensor_events);
        vSemaphoreDelete(s_display_mutex);
        vSemaphoreDelete(s_state_mutex);
        s_sensor_events = NULL;
        s_display_mutex = NULL;
        s_state_mutex = NULL;
        return ESP_ERR_NO_MEM;
    }

    for (size_t sensor_index = 0; sensor_index < THERMOMETER_SENSOR_COUNT;
         ++sensor_index) {
        task_created = xTaskCreate(
            sensor_acquisition_task, "sensor_acquisition",
            THERMOMETER_SAMPLING_TASK_STACK_BYTES,
            (void *)(uintptr_t)sensor_index,
            THERMOMETER_SAMPLING_TASK_PRIORITY, &s_sensor_tasks[sensor_index]);
        if (task_created != pdPASS) {
            for (size_t created = 0; created < sensor_index; ++created) {
                vTaskDelete(s_sensor_tasks[created]);
            }
            vTaskDelete(s_state_task);
            vQueueDelete(s_sensor_events);
            vSemaphoreDelete(s_display_mutex);
            vSemaphoreDelete(s_state_mutex);
            s_sensor_events = NULL;
            s_display_mutex = NULL;
            s_state_mutex = NULL;
            return ESP_ERR_NO_MEM;
        }
    }

    s_started = true;
    return ESP_OK;
}

void thermometer_get_current(thermometer_current_snapshot_t *snapshot)
{
    if (snapshot == NULL) {
        return;
    }

    /* Requirement: SWE-EMB-LLR-324 (SCRUM-494). Return one atomic snapshot. */
    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    copy_current_snapshot_locked(snapshot);
    xSemaphoreGive(s_state_mutex);
}

void thermometer_get_history_meta(thermometer_history_meta_t *meta)
{
    if (meta == NULL) {
        return;
    }

    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    meta->boot_id = s_boot_id;
    meta->newest_sequence = s_latest_sequence;
    for (size_t sensor_index = 0; sensor_index < THERMOMETER_SENSOR_COUNT;
         ++sensor_index) {
        const sensor_runtime_t *sensor = &s_sensors[sensor_index];
        meta->counts[sensor_index] = history_buffer_count(&sensor->history);
        meta->oldest_sequences[sensor_index] =
            history_buffer_oldest_sequence(&sensor->history);
    }
    xSemaphoreGive(s_state_mutex);
}

bool thermometer_set_display(uint8_t sensor_id, bool enabled,
                             thermometer_visible_state_t *resulting_state,
                             bool *resulting_enabled)
{
    if (sensor_id == 0U || sensor_id > THERMOMETER_SENSOR_COUNT) {
        return false;
    }

    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    thermometer_sensor_snapshot_t *sensor =
        &s_sensors[sensor_id - 1U].latest;
    const bool available = sensor_is_available(sensor);
    const bool state_changed = available && sensor->display_enabled != enabled;
    if (available) {
        /* Requirement: SWE-EMB-LLR-327 (SCRUM-497). One local/BLE state path. */
        sensor->display_enabled = enabled;
    }
    if (resulting_state != NULL) {
        *resulting_state = thermometer_visible_state(sensor);
    }
    if (resulting_enabled != NULL) {
        *resulting_enabled = sensor->display_enabled;
    }
    xSemaphoreGive(s_state_mutex);

    if (state_changed) {
        render_current_display();
    }
    return available;
}

bool thermometer_toggle_display(uint8_t sensor_id)
{
    if (sensor_id == 0U || sensor_id > THERMOMETER_SENSOR_COUNT) {
        return false;
    }

    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    thermometer_sensor_snapshot_t *sensor =
        &s_sensors[sensor_id - 1U].latest;
    const bool available = sensor_is_available(sensor);
    if (available) {
        sensor->display_enabled = !sensor->display_enabled;
    }
    xSemaphoreGive(s_state_mutex);

    if (available) {
        render_current_display();
    }
    return available;
}

esp_err_t thermometer_set_backlight(uint8_t brightness_percent)
{
    if (brightness_percent > 100U) {
        return ESP_ERR_INVALID_ARG;
    }
    xSemaphoreTake(s_display_mutex, portMAX_DELAY);
    const esp_err_t result = local_display_set_backlight(brightness_percent);
    xSemaphoreGive(s_display_mutex);
    return result;
}

bool thermometer_copy_history(uint8_t sensor_id, uint32_t start_sequence,
                              size_t requested_count,
                              thermometer_history_record_t *records,
                              size_t *copied_count)
{
    if (sensor_id == 0U || sensor_id > THERMOMETER_SENSOR_COUNT ||
        records == NULL || copied_count == NULL) {
        return false;
    }
    *copied_count = 0U;

    xSemaphoreTake(s_state_mutex, portMAX_DELAY);
    const bool copied = history_buffer_copy(
        &s_sensors[sensor_id - 1U].history, start_sequence, requested_count,
        records, copied_count);
    xSemaphoreGive(s_state_mutex);
    return copied;
}
