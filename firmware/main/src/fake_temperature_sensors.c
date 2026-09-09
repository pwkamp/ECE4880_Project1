#include "temperature_sensors.h"

#include "thermometer_config.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

typedef struct {
    int16_t center_centi_c;
    int16_t amplitude_centi_c;
    uint32_t wave_period_samples;
    uint32_t wave_offset_samples;
    uint32_t disconnect_start_sample;
    uint32_t disconnect_end_sample;
} fake_sensor_profile_t;

static const fake_sensor_profile_t SENSOR_PROFILES[THERMOMETER_SENSOR_COUNT] = {
    {
        .center_centi_c = THERMOMETER_FAKE_SENSOR_1_CENTER_CENTI_C,
        .amplitude_centi_c = THERMOMETER_FAKE_SENSOR_1_AMPLITUDE_CENTI_C,
        .wave_period_samples = THERMOMETER_FAKE_SENSOR_1_WAVE_PERIOD_SAMPLES,
        .wave_offset_samples = THERMOMETER_FAKE_SENSOR_1_WAVE_OFFSET_SAMPLES,
        .disconnect_start_sample =
            THERMOMETER_FAKE_SENSOR_1_DISCONNECT_START_SAMPLE,
        .disconnect_end_sample =
            THERMOMETER_FAKE_SENSOR_1_DISCONNECT_END_SAMPLE,
    },
    {
        .center_centi_c = THERMOMETER_FAKE_SENSOR_2_CENTER_CENTI_C,
        .amplitude_centi_c = THERMOMETER_FAKE_SENSOR_2_AMPLITUDE_CENTI_C,
        .wave_period_samples = THERMOMETER_FAKE_SENSOR_2_WAVE_PERIOD_SAMPLES,
        .wave_offset_samples = THERMOMETER_FAKE_SENSOR_2_WAVE_OFFSET_SAMPLES,
        .disconnect_start_sample =
            THERMOMETER_FAKE_SENSOR_2_DISCONNECT_START_SAMPLE,
        .disconnect_end_sample =
            THERMOMETER_FAKE_SENSOR_2_DISCONNECT_END_SAMPLE,
    },
};

static bool is_connected(const fake_sensor_profile_t *profile,
                         uint32_t sample_number)
{
    if (!THERMOMETER_FAKE_DISCONNECTS) {
        return true;
    }

    const uint32_t cycle_position =
        sample_number % THERMOMETER_FAKE_DISCONNECT_CYCLE_SAMPLES;
    return cycle_position < profile->disconnect_start_sample ||
           cycle_position >= profile->disconnect_end_sample;
}

static int16_t triangle_wave(const fake_sensor_profile_t *profile,
                             uint32_t sample_number)
{
    const uint32_t position =
        (sample_number + profile->wave_offset_samples) %
        profile->wave_period_samples;
    const uint32_t half_period = profile->wave_period_samples / 2U;
    const uint32_t distance_from_low =
        position < half_period ? position : profile->wave_period_samples - position;
    const int32_t excursion =
        ((int32_t)distance_from_low * 2 * profile->amplitude_centi_c) /
        (int32_t)half_period;
    return (int16_t)(profile->center_centi_c - profile->amplitude_centi_c +
                     excursion);
}

esp_err_t temperature_sensors_init(void)
{
    return ESP_OK;
}

temperature_sensor_reading_t temperature_sensor_read(size_t sensor_index,
                                                     uint32_t sample_number)
{
    /*
     * Simulation support for SWE-EMB-LLR-302..303 (SCRUM-472..473). Each
     * profile evolves and disconnects independently;
     * every value comes from the shared JSON rather than a source-code literal.
     */
    temperature_sensor_reading_t reading = {0};
    if (sensor_index >= THERMOMETER_SENSOR_COUNT) {
        return reading;
    }

    vTaskDelay(pdMS_TO_TICKS(THERMOMETER_SAMPLE_PERIOD_MS));

    const fake_sensor_profile_t *profile = &SENSOR_PROFILES[sensor_index];
    reading.valid = is_connected(profile, sample_number);
    if (reading.valid) {
        reading.temperature_centi_c = triangle_wave(profile, sample_number);
    }
    return reading;
}
