#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "thermometer.h"

typedef struct {
    thermometer_history_record_t records[THERMOMETER_HISTORY_CAPACITY];
    uint16_t next_index;
    uint16_t count;
} thermometer_history_buffer_t;

void history_buffer_init(thermometer_history_buffer_t *buffer);
void history_buffer_append(thermometer_history_buffer_t *buffer,
                           thermometer_history_record_t record);
uint16_t history_buffer_count(const thermometer_history_buffer_t *buffer);
uint32_t history_buffer_oldest_sequence(
    const thermometer_history_buffer_t *buffer);
bool history_buffer_copy(const thermometer_history_buffer_t *buffer,
                         uint32_t start_sequence, size_t requested_count,
                         thermometer_history_record_t *records,
                         size_t *copied_count);
