#include "identity.h"

#include <stdio.h>
#include <string.h>

#include "esp_random.h"
#include "nvs.h"

#define DM_NAMESPACE "dm_identity"
#define DM_ID_KEY "agent_id"
#define DM_POP_KEY "provisioning_pop"

static char s_agent_id[37];
static char s_provisioning_pop[17];

static int generate_id(char *buffer, size_t capacity) {
    if (!buffer || capacity < sizeof(s_agent_id)) return -1;
    unsigned char bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;
    int written = snprintf(
        buffer,
        capacity,
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5], bytes[6], bytes[7],
        bytes[8], bytes[9], bytes[10], bytes[11],
        bytes[12], bytes[13], bytes[14], bytes[15]
    );
    return written == 36 ? 0 : -1;
}

static int generate_pop(char *buffer, size_t capacity) {
    if (!buffer || capacity < sizeof(s_provisioning_pop)) return -1;
    unsigned char bytes[8];
    esp_fill_random(bytes, sizeof(bytes));
    int written = snprintf(
        buffer,
        capacity,
        "%02x%02x%02x%02x%02x%02x%02x%02x",
        bytes[0], bytes[1], bytes[2], bytes[3],
        bytes[4], bytes[5], bytes[6], bytes[7]
    );
    return written == 16 ? 0 : -1;
}

int dm_identity_init(void) {
    nvs_handle_t handle;
    if (nvs_open(DM_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;

    bool changed = false;
    size_t length = sizeof(s_agent_id);
    esp_err_t err = nvs_get_str(handle, DM_ID_KEY, s_agent_id, &length);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        if (generate_id(s_agent_id, sizeof(s_agent_id)) != 0) {
            nvs_close(handle);
            return -1;
        }
        err = nvs_set_str(handle, DM_ID_KEY, s_agent_id);
        changed = err == ESP_OK;
    }
    if (err != ESP_OK) {
        nvs_close(handle);
        return -1;
    }

    length = sizeof(s_provisioning_pop);
    err = nvs_get_str(handle, DM_POP_KEY, s_provisioning_pop, &length);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        if (generate_pop(s_provisioning_pop, sizeof(s_provisioning_pop)) != 0) {
            nvs_close(handle);
            return -1;
        }
        err = nvs_set_str(handle, DM_POP_KEY, s_provisioning_pop);
        changed = changed || err == ESP_OK;
    }
    if (err == ESP_OK && changed) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_identity_get(char *buffer, size_t capacity) {
    size_t length = strlen(s_agent_id);
    if (!buffer || capacity <= length || length != 36) return -1;
    memcpy(buffer, s_agent_id, length + 1);
    return 0;
}

int dm_identity_get_provisioning_pop(char *buffer, size_t capacity) {
    size_t length = strlen(s_provisioning_pop);
    if (!buffer || capacity <= length || length != 16) return -1;
    memcpy(buffer, s_provisioning_pop, length + 1);
    return 0;
}
