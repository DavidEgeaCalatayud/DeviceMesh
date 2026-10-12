#pragma once

#include <stdint.h>

#include "telemetry.h"

#define DM_QUEUE_MAGIC 0x444D5131U
#define DM_QUEUE_CAPACITY 64U

typedef struct {
    uint32_t magic;
    uint32_t head;
    uint32_t count;
    dm_telemetry_t samples[DM_QUEUE_CAPACITY];
} dm_queue_state_t;

void dm_queue_reset(dm_queue_state_t *queue);
int dm_queue_valid(const dm_queue_state_t *queue);
int dm_queue_push(dm_queue_state_t *queue, const dm_telemetry_t *sample);
int dm_queue_peek(const dm_queue_state_t *queue, dm_telemetry_t *sample);
int dm_queue_pop(dm_queue_state_t *queue);
