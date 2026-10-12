#include "offline_queue.h"

#include "nvs.h"
#include "telemetry_queue.h"

#define QUEUE_NAMESPACE "dm_queue"
#define QUEUE_KEY "telemetry"

static dm_queue_state_t s_queue;

static int persist(void) {
    nvs_handle_t handle;
    if (nvs_open(QUEUE_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_set_blob(handle, QUEUE_KEY, &s_queue, sizeof(s_queue));
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_offline_queue_init(void) {
    dm_queue_reset(&s_queue);

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
        !dm_queue_valid(&s_queue)
    ) {
        dm_queue_reset(&s_queue);
        return persist();
    }
    return 0;
}

int dm_offline_queue_push(const dm_telemetry_t *sample) {
    if (dm_queue_push(&s_queue, sample) != 0) return -1;
    return persist();
}

int dm_offline_queue_peek(dm_telemetry_t *sample) {
    return dm_queue_peek(&s_queue, sample);
}

int dm_offline_queue_pop(void) {
    if (dm_queue_pop(&s_queue) != 0) return -1;
    return persist();
}

unsigned dm_offline_queue_count(void) {
    return s_queue.count;
}

int dm_offline_queue_clear(void) {
    dm_queue_reset(&s_queue);
    return persist();
}
