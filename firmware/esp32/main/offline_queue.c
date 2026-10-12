#include "offline_queue.h"

#include <string.h>

#include "nvs.h"

#define QUEUE_NAMESPACE "dm_queue"
#define QUEUE_KEY "telemetry"
#define QUEUE_MAGIC 0x444D5131U
#define QUEUE_CAPACITY 64U

typedef struct {
    uint32_t magic;
    uint32_t head;
    uint32_t count;
    dm_telemetry_t samples[QUEUE_CAPACITY];
} queue_state_t;

static queue_state_t s_queue;

static int persist(void) {
    nvs_handle_t handle;
    if (nvs_open(QUEUE_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_set_blob(handle, QUEUE_KEY, &s_queue, sizeof(s_queue));
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_offline_queue_init(void) {
    memset(&s_queue, 0, sizeof(s_queue));
    s_queue.magic = QUEUE_MAGIC;

    nvs_handle_t handle;
    if (nvs_open(QUEUE_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) {
        return persist();
    }
    size_t length = sizeof(s_queue);
    esp_err_t err = nvs_get_blob(handle, QUEUE_KEY, &s_queue, &length);
    nvs_close(handle);
    if (
        err != ESP_OK ||
        length != sizeof(s_queue) ||
        s_queue.magic != QUEUE_MAGIC ||
        s_queue.head >= QUEUE_CAPACITY ||
        s_queue.count > QUEUE_CAPACITY
    ) {
        memset(&s_queue, 0, sizeof(s_queue));
        s_queue.magic = QUEUE_MAGIC;
        return persist();
    }
    return 0;
}

int dm_offline_queue_push(const dm_telemetry_t *sample) {
    if (!sample) return -1;
    uint32_t index = (s_queue.head + s_queue.count) % QUEUE_CAPACITY;
    if (s_queue.count == QUEUE_CAPACITY) {
        index = s_queue.head;
        s_queue.head = (s_queue.head + 1U) % QUEUE_CAPACITY;
    } else {
        s_queue.count++;
    }
    s_queue.samples[index] = *sample;
    return persist();
}

int dm_offline_queue_peek(dm_telemetry_t *sample) {
    if (!sample || s_queue.count == 0U) return -1;
    *sample = s_queue.samples[s_queue.head];
    return 0;
}

int dm_offline_queue_pop(void) {
    if (s_queue.count == 0U) return -1;
    memset(&s_queue.samples[s_queue.head], 0, sizeof(dm_telemetry_t));
    s_queue.head = (s_queue.head + 1U) % QUEUE_CAPACITY;
    s_queue.count--;
    return persist();
}

unsigned dm_offline_queue_count(void) {
    return s_queue.count;
}
