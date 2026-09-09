#include "history_buffer.h"

#include <string.h>

static uint16_t oldest_index(const thermometer_history_buffer_t *buffer)
{
    return (uint16_t)((buffer->next_index + THERMOMETER_HISTORY_CAPACITY -
                       buffer->count) %
                      THERMOMETER_HISTORY_CAPACITY);
}

void history_buffer_init(thermometer_history_buffer_t *buffer)
{
    if (buffer != NULL) {
        memset(buffer, 0, sizeof(*buffer));
    }
}

void history_buffer_append(thermometer_history_buffer_t *buffer,
                           thermometer_history_record_t record)
{
    if (buffer == NULL) {
        return;
    }
    buffer->records[buffer->next_index] = record;
    buffer->next_index = (uint16_t)((buffer->next_index + 1U) %
                                    THERMOMETER_HISTORY_CAPACITY);
    if (buffer->count < THERMOMETER_HISTORY_CAPACITY) {
        ++buffer->count;
    }
}

uint16_t history_buffer_count(const thermometer_history_buffer_t *buffer)
{
    return buffer == NULL ? 0U : buffer->count;
}

uint32_t history_buffer_oldest_sequence(
    const thermometer_history_buffer_t *buffer)
{
    if (buffer == NULL || buffer->count == 0U) {
        return 0U;
    }
    return buffer->records[oldest_index(buffer)].sequence;
}

bool history_buffer_copy(const thermometer_history_buffer_t *buffer,
                         uint32_t start_sequence, size_t requested_count,
                         thermometer_history_record_t *records,
                         size_t *copied_count)
{
    if (buffer == NULL || records == NULL || copied_count == NULL) {
        return false;
    }
    *copied_count = 0U;
    const uint16_t first = oldest_index(buffer);
    size_t start_offset = 0U;
    while (start_offset < buffer->count) {
        const uint16_t index = (uint16_t)(
            (first + start_offset) % THERMOMETER_HISTORY_CAPACITY);
        if (buffer->records[index].sequence == start_sequence) {
            break;
        }
        ++start_offset;
    }
    if (start_offset == buffer->count) {
        return false;
    }

    const size_t available = buffer->count - start_offset;
    const size_t count = requested_count < available ? requested_count : available;
    for (size_t offset = 0; offset < count; ++offset) {
        const uint16_t index = (uint16_t)(
            (first + start_offset + offset) % THERMOMETER_HISTORY_CAPACITY);
        records[offset] = buffer->records[index];
    }
    *copied_count = count;
    return count > 0U;
}
