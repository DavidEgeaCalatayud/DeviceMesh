#include "telemetry_queue.h"

#include <string.h>

void dm_queue_reset(dm_queue_state_t *queue) {
    if (!queue) return;
    memset(queue, 0, sizeof(*queue));
    queue->magic = DM_QUEUE_MAGIC;
}

int dm_queue_valid(const dm_queue_state_t *queue) {
    return queue &&
        queue->magic == DM_QUEUE_MAGIC &&
        queue->head < DM_QUEUE_CAPACITY &&
        queue->count <= DM_QUEUE_CAPACITY;
}

int dm_queue_push(dm_queue_state_t *queue, const dm_telemetry_t *sample) {
    if (!dm_queue_valid(queue) || !sample) return -1;
    uint32_t index = (queue->head + queue->count) % DM_QUEUE_CAPACITY;
    if (queue->count == DM_QUEUE_CAPACITY) {
        index = queue->head;
        queue->head = (queue->head + 1U) % DM_QUEUE_CAPACITY;
    } else {
        queue->count++;
    }
    queue->samples[index] = *sample;
    return 0;
}

int dm_queue_peek(const dm_queue_state_t *queue, dm_telemetry_t *sample) {
    if (!dm_queue_valid(queue) || !sample || queue->count == 0U) return -1;
    *sample = queue->samples[queue->head];
    return 0;
}

int dm_queue_pop(dm_queue_state_t *queue) {
    if (!dm_queue_valid(queue) || queue->count == 0U) return -1;
    memset(&queue->samples[queue->head], 0, sizeof(dm_telemetry_t));
    queue->head = (queue->head + 1U) % DM_QUEUE_CAPACITY;
    queue->count--;
    return 0;
}
