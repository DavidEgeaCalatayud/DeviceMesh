#include "storage.h"

#include <stdio.h>
#include <string.h>

#include "esp_mac.h"
#include "esp_system.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *NS = "devicemesh";

static int get_string(nvs_handle_t handle, const char *key, char *out, size_t capacity) {
    size_t needed = capacity;
    esp_err_t err = nvs_get_str(handle, key, out, &needed);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        if (capacity) out[0] = '\0';
        return 0;
    }
    return err == ESP_OK ? 0 : -1;
}

int dm_storage_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        if (nvs_flash_erase() != ESP_OK) return -1;
        err = nvs_flash_init();
    }
    return err == ESP_OK ? 0 : -1;
}

int dm_storage_load(dm_config_t *out) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    nvs_handle_t handle;
    if (nvs_open(NS, NVS_READONLY, &handle) != ESP_OK) return 0;
    int rc = 0;
    rc |= get_string(handle, "ssid", out->ssid, sizeof(out->ssid));
    rc |= get_string(handle, "password", out->password, sizeof(out->password));
    rc |= get_string(handle, "server", out->server_url, sizeof(out->server_url));
    rc |= get_string(handle, "enroll", out->enrollment_token, sizeof(out->enrollment_token));
    rc |= get_string(handle, "credential", out->agent_credential, sizeof(out->agent_credential));
    rc |= get_string(handle, "probe_host", out->probe_host, sizeof(out->probe_host));
    nvs_close(handle);
    return rc == 0 ? 0 : -1;
}

int dm_storage_save_provisioning(const dm_config_t *config) {
    if (!config) return -1;
    nvs_handle_t handle;
    if (nvs_open(NS, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_set_str(handle, "ssid", config->ssid);
    if (err == ESP_OK) err = nvs_set_str(handle, "password", config->password);
    if (err == ESP_OK) err = nvs_set_str(handle, "server", config->server_url);
    if (err == ESP_OK) err = nvs_set_str(handle, "enroll", config->enrollment_token);
    if (err == ESP_OK) err = nvs_set_str(handle, "probe_host", config->probe_host);
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_storage_save_credential(const char *credential) {
    if (!credential || !credential[0]) return -1;
    nvs_handle_t handle;
    if (nvs_open(NS, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_set_str(handle, "credential", credential);
    if (err == ESP_OK) {
        err = nvs_erase_key(handle, "enroll");
        if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    }
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_storage_clear_credential(void) {
    nvs_handle_t handle;
    if (nvs_open(NS, NVS_READWRITE, &handle) != ESP_OK) return -1;
    esp_err_t err = nvs_erase_key(handle, "credential");
    if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    return err == ESP_OK ? 0 : -1;
}

int dm_identity(char *buffer, size_t capacity) {
    if (!buffer || capacity < 20) return -1;
    uint8_t mac[6];
    if (esp_read_mac(mac, ESP_MAC_WIFI_STA) != ESP_OK) return -1;
    int written = snprintf(
        buffer,
        capacity,
        "esp32-%02x%02x%02x%02x%02x%02x",
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
    );
    return written > 0 && (size_t)written < capacity ? 0 : -1;
}

bool dm_config_is_provisioned(const dm_config_t *config) {
    return config && config->ssid[0] && config->server_url[0] &&
           (config->enrollment_token[0] || config->agent_credential[0]);
}
