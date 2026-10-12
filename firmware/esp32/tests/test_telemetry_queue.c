#include <assert.h>
#include <stdio.h>

#include "telemetry_queue.h"

static dm_telemetry_t sample(long long timestamp) {
    dm_telemetry_t value = {0};
    value.sampled_at_unix = timestamp;
    value.wifi_rssi = (int)(timestamp % 100);
    return value;
}

int main(void) {
    dm_queue_state_t queue;
    dm_queue_reset(&queue);
    assert(dm_queue_valid(&queue));
    assert(queue.count == 0U);

    dm_telemetry_t out;
    assert(dm_queue_peek(&queue, &out) == -1);
    assert(dm_queue_pop(&queue) == -1);

    for (unsigned index = 0; index < DM_QUEUE_CAPACITY; index++) {
        dm_telemetry_t value = sample((long long)index);
        assert(dm_queue_push(&queue, &value) == 0);
    }
    assert(queue.count == DM_QUEUE_CAPACITY);
    assert(dm_queue_peek(&queue, &out) == 0);
    assert(out.sampled_at_unix == 0);

    dm_telemetry_t overflow = sample(64);
    assert(dm_queue_push(&queue, &overflow) == 0);
    assert(queue.count == DM_QUEUE_CAPACITY);
    assert(dm_queue_peek(&queue, &out) == 0);
    assert(out.sampled_at_unix == 1);

    for (long long expected = 1; expected <= 64; expected++) {
        assert(dm_queue_peek(&queue, &out) == 0);
        assert(out.sampled_at_unix == expected);
        assert(dm_queue_pop(&queue) == 0);
    }
    assert(queue.count == 0U);
    assert(dm_queue_peek(&queue, &out) == -1);

    queue.magic = 0;
    assert(!dm_queue_valid(&queue));
    assert(dm_queue_push(&queue, &overflow) == -1);

    puts("telemetry queue tests passed");
    return 0;
}
