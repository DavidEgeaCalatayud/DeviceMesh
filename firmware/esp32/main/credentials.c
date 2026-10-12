#include "credentials.h"

#include <string.h>

#include "nvs.h"

#define DM_NAMESPACE "dm_secrets"

static int set_value(const char *key, const char *value) {
    if (!value || !value[0]) return -1;
    nvs_handle_t handle;
    if (nvs_open(DM_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_set_str(handle, key, value);
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

static int get_value(const char *key, char *buffer, size_t capacity) {
    if (!buffer || capacity < 2) return -1;
    nvs_handle_t handle;
    if (nvs_open(DM_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) return -1;
    size_t length = capacity;
    esp_err_t err = nvs_get_str(handle, key, buffer, &length);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_credentials_set_server(const char *server_url) {
    if (!server_url || strncmp(server_url, "https://", 8) != 0) return -1;
    return set_value("server", server_url);
}

int dm_credentials_get_server(char *buffer, size_t capacity) {
    return get_value("server", buffer, capacity);
}

int dm_credentials_set_enrollment_token(const char *token) {
    return set_value("enroll", token);
}

int dm_credentials_get_enrollment_token(char *buffer, size_t capacity) {
    return get_value("enroll", buffer, capacity);
}

int dm_credentials_clear_enrollment_token(void) {
    nvs_handle_t handle;
    if (nvs_open(DM_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_erase_key(handle, "enroll");
    if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_credentials_set_agent_credential(const char *credential_id, const char *credential) {
    if (set_value("cred_id", credential_id) != 0) return -1;
    return set_value("credential", credential);
}

int dm_credentials_get_agent_credential(
    char *credential_id,
    size_t credential_id_capacity,
    char *credential,
    size_t credential_capacity
) {
    if (get_value("cred_id", credential_id, credential_id_capacity) != 0) return -1;
    return get_value("credential", credential, credential_capacity);
}


int dm_credentials_clear_all(void) {
    nvs_handle_t handle;
    if (nvs_open(DM_NAMESPACE, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_erase_all(handle);
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}
