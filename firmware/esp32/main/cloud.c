#include "cloud.h"

#include <stdio.h>
#include <string.h>
#include <time.h>

#include "cJSON.h"
#include "credentials.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_random.h"

static const char *TAG = "dm_cloud";

static int build_url(char *out, size_t capacity, const char *server, const char *path) {
    int written = snprintf(out, capacity, "%s%s", server, path);
    return written > 0 && (size_t)written < capacity ? 0 : -1;
}

static esp_err_t http_json(
    const char *url,
    const char *body,
    const char *agent_id,
    const char *credential,
    char *response,
    size_t response_capacity
) {
    esp_http_client_config_t config = {
        .url = url,
        .timeout_ms = 15000,
        .crt_bundle_attach = esp_crt_bundle_attach,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return ESP_FAIL;

    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Accept", "application/json");
    esp_http_client_set_header(client, "Content-Type", "application/json");

    if (credential && agent_id) {
        char authorization[320];
        snprintf(authorization, sizeof(authorization), "Agent %s", credential);
        esp_http_client_set_header(client, "Authorization", authorization);
        esp_http_client_set_header(client, "X-DeviceMesh-Agent-ID", agent_id);

        time_t now = time(NULL);
        struct tm utc;
        gmtime_r(&now, &utc);
        char timestamp[32];
        strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
        esp_http_client_set_header(client, "X-DeviceMesh-Timestamp", timestamp);

        char nonce_text[24];
        snprintf(
            nonce_text,
            sizeof(nonce_text),
            "%08lx-%08lx",
            (unsigned long)esp_random(),
            (unsigned long)esp_random()
        );
        esp_http_client_set_header(client, "X-DeviceMesh-Nonce", nonce_text);
    }

    if (body) {
        esp_http_client_set_post_field(client, body, strlen(body));
    }

    esp_err_t err = esp_http_client_perform(client);
    int status = err == ESP_OK ? esp_http_client_get_status_code(client) : 0;
    if (err == ESP_OK && response && response_capacity > 1) {
        int read = esp_http_client_read_response(client, response, response_capacity - 1);
        if (read >= 0) response[read] = '\0';
    }
    esp_http_client_cleanup(client);
    if (err != ESP_OK) return err;
    return status >= 200 && status < 300 ? ESP_OK : ESP_FAIL;
}

int dm_cloud_enroll_if_needed(const char *agent_id) {
    char credential_id[64];
    char credential[256];
    if (dm_credentials_get_agent_credential(
            credential_id,
            sizeof(credential_id),
            credential,
            sizeof(credential)
        ) == 0) {
        return 0;
    }

    char server[256];
    char token[256];
    if (dm_credentials_get_server(server, sizeof(server)) != 0 ||
        dm_credentials_get_enrollment_token(token, sizeof(token)) != 0) {
        ESP_LOGW(TAG, "Cloud enrollment configuration missing");
        return -1;
    }

    char url[320];
    if (build_url(url, sizeof(url), server, "/api/v1/agents/enroll") != 0) return -1;

    cJSON *root = cJSON_CreateObject();
    if (!root) return -1;
    cJSON_AddStringToObject(root, "token", token);
    cJSON_AddStringToObject(root, "agentId", agent_id);
    char *body = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (!body) return -1;

    char response[768] = {0};
    esp_err_t err = http_json(url, body, NULL, NULL, response, sizeof(response));
    cJSON_free(body);
    if (err != ESP_OK) return -1;

    cJSON *payload = cJSON_Parse(response);
    if (!payload) return -1;
    cJSON *id = cJSON_GetObjectItemCaseSensitive(payload, "credentialId");
    cJSON *secret = cJSON_GetObjectItemCaseSensitive(payload, "credential");
    int result = -1;
    if (cJSON_IsString(id) && cJSON_IsString(secret) &&
        dm_credentials_set_agent_credential(id->valuestring, secret->valuestring) == 0) {
        dm_credentials_clear_enrollment_token();
        result = 0;
    }
    cJSON_Delete(payload);
    return result;
}

int dm_cloud_send_heartbeat(const char *agent_id, const dm_telemetry_t *telemetry) {
    if (!agent_id || !telemetry) return -1;

    char server[256];
    char credential_id[64];
    char credential[256];
    if (dm_credentials_get_server(server, sizeof(server)) != 0 ||
        dm_credentials_get_agent_credential(
            credential_id,
            sizeof(credential_id),
            credential,
            sizeof(credential)
        ) != 0) {
        return -1;
    }

    time_t now = time(NULL);
    if (now < 1704067200) {
        ESP_LOGW(TAG, "System clock not synchronized yet");
        return -1;
    }
    struct tm utc;
    gmtime_r(&now, &utc);
    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);

    cJSON *root = cJSON_CreateObject();
    if (!root) return -1;
    cJSON_AddStringToObject(root, "type", "heartbeat");
    cJSON_AddNumberToObject(root, "protocolVersion", 1);
    cJSON_AddStringToObject(root, "agentId", agent_id);
    cJSON_AddStringToObject(root, "timestamp", timestamp);

    cJSON *device = cJSON_AddObjectToObject(root, "device");
    cJSON_AddStringToObject(device, "hostname", agent_id);
    cJSON_AddStringToObject(device, "operatingSystem", "esp-idf");
    cJSON_AddStringToObject(device, "architecture", "xtensa");
    cJSON_AddStringToObject(device, "manufacturer", "Espressif");
    cJSON_AddArrayToObject(device, "ipAddresses");
    cJSON_AddArrayToObject(device, "macAddresses");

    char *body = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (!body) return -1;

    char url[320];
    int result = -1;
    if (build_url(url, sizeof(url), server, "/api/v1/agents/heartbeat") == 0 &&
        http_json(url, body, agent_id, credential, NULL, 0) == ESP_OK) {
        result = 0;
    }
    cJSON_free(body);
    return result;
}
