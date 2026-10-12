#include "ble.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "credentials.h"
#include "esp_log.h"
#include "wifi_provisioning/manager.h"
#include "wifi_provisioning/scheme_ble.h"

static const char *TAG = "dm_provisioning";
static const char *CONFIG_ENDPOINT = "devicemesh-config";

static esp_err_t config_endpoint_handler(
    uint32_t session_id,
    const uint8_t *inbuf,
    ssize_t inlen,
    uint8_t **outbuf,
    ssize_t *outlen,
    void *priv_data
) {
    (void)session_id;
    (void)priv_data;
    if (!inbuf || inlen <= 0 || !outbuf || !outlen || inlen > 2048) {
        return ESP_ERR_INVALID_ARG;
    }

    char *json = calloc((size_t)inlen + 1U, 1U);
    if (!json) return ESP_ERR_NO_MEM;
    memcpy(json, inbuf, (size_t)inlen);

    cJSON *root = cJSON_Parse(json);
    free(json);
    if (!root) return ESP_ERR_INVALID_ARG;

    cJSON *server = cJSON_GetObjectItemCaseSensitive(root, "serverUrl");
    cJSON *token = cJSON_GetObjectItemCaseSensitive(root, "enrollmentToken");
    esp_err_t result = ESP_FAIL;

    if (
        cJSON_IsString(server) &&
        cJSON_IsString(token) &&
        server->valuestring &&
        token->valuestring &&
        strlen(server->valuestring) <= 255 &&
        strlen(token->valuestring) <= 255 &&
        dm_credentials_set_server(server->valuestring) == 0 &&
        dm_credentials_set_enrollment_token(token->valuestring) == 0
    ) {
        const char response[] = "{\"status\":\"ok\"}";
        *outbuf = (uint8_t *)strdup(response);
        if (*outbuf) {
            *outlen = (ssize_t)strlen(response);
            result = ESP_OK;
        } else {
            result = ESP_ERR_NO_MEM;
        }
    } else {
        const char response[] = "{\"status\":\"invalid_config\"}";
        *outbuf = (uint8_t *)strdup(response);
        if (*outbuf) {
            *outlen = (ssize_t)strlen(response);
            result = ESP_OK;
        } else {
            result = ESP_ERR_NO_MEM;
        }
    }

    cJSON_Delete(root);
    return result;
}

int dm_ble_init(const char *device_id) {
    if (!device_id || strlen(device_id) < 8) return -1;

    wifi_prov_mgr_config_t config = {
        .scheme = wifi_prov_scheme_ble,
        .scheme_event_handler = WIFI_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM,
    };
    if (wifi_prov_mgr_init(config) != ESP_OK) return -1;

    bool provisioned = false;
    if (wifi_prov_mgr_is_provisioned(&provisioned) != ESP_OK) {
        wifi_prov_mgr_deinit();
        return -1;
    }
    if (provisioned) {
        ESP_LOGI(TAG, "Wi-Fi already provisioned");
        wifi_prov_mgr_deinit();
        return 0;
    }

    char service_name[16];
    const char *suffix = device_id + strlen(device_id) - 6;
    snprintf(service_name, sizeof(service_name), "DM-%s", suffix);

    char pop[13];
    snprintf(pop, sizeof(pop), "%.12s", device_id);
    ESP_LOGI(TAG, "BLE provisioning service %s", service_name);
    ESP_LOGI(TAG, "Provisioning proof-of-possession: %s", pop);

    if (wifi_prov_mgr_endpoint_create(CONFIG_ENDPOINT) != ESP_OK) {
        wifi_prov_mgr_deinit();
        return -1;
    }

    esp_err_t err = wifi_prov_mgr_start_provisioning(
        WIFI_PROV_SECURITY_1,
        pop,
        service_name,
        NULL
    );
    if (err != ESP_OK) {
        wifi_prov_mgr_deinit();
        return -1;
    }

    err = wifi_prov_mgr_endpoint_register(
        CONFIG_ENDPOINT,
        config_endpoint_handler,
        NULL
    );
    if (err != ESP_OK) {
        wifi_prov_mgr_stop_provisioning();
        wifi_prov_mgr_deinit();
        return -1;
    }

    ESP_LOGI(TAG, "DeviceMesh config endpoint ready");
    return 1;
}
