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
    size_t response_capacity,
    int *status_out
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
    if (status_out) *status_out = status;
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
    esp_err_t err = http_json(url, body, NULL, NULL, response, sizeof(response), NULL);
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
        http_json(url, body, agent_id, credential, NULL, 0, NULL) == ESP_OK) {
        result = 0;
    }
    cJSON_free(body);
    return result;
}


int dm_cloud_send_telemetry(const char *agent_id, const dm_telemetry_t *telemetry) {
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

    time_t now = telemetry->sampled_at_unix > 0
        ? (time_t)telemetry->sampled_at_unix
        : time(NULL);
    if (now < 1704067200) return -1;
    struct tm utc;
    gmtime_r(&now, &utc);
    char timestamp[32];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", &utc);

    cJSON *root = cJSON_CreateObject();
    if (!root) return -1;
    cJSON_AddStringToObject(root, "type", "telemetry");
    cJSON_AddNumberToObject(root, "protocolVersion", 1);
    cJSON_AddStringToObject(root, "agentId", agent_id);
    cJSON_AddStringToObject(root, "timestamp", timestamp);
    cJSON *metrics = cJSON_AddArrayToObject(root, "metrics");

    cJSON *rssi = cJSON_CreateObject();
    cJSON_AddStringToObject(rssi, "name", "network.wifi.rssi.dbm");
    cJSON_AddNumberToObject(rssi, "value", telemetry->wifi_rssi);
    cJSON_AddStringToObject(rssi, "unit", "dBm");
    cJSON_AddItemToArray(metrics, rssi);

    cJSON *heap = cJSON_CreateObject();
    cJSON_AddStringToObject(heap, "name", "memory.free.bytes");
    cJSON_AddNumberToObject(heap, "value", telemetry->free_heap_bytes);
    cJSON_AddStringToObject(heap, "unit", "bytes");
    cJSON_AddItemToArray(metrics, heap);

    cJSON *uptime = cJSON_CreateObject();
    cJSON_AddStringToObject(uptime, "name", "system.uptime.seconds");
    cJSON_AddNumberToObject(uptime, "value", (double)telemetry->uptime_seconds);
    cJSON_AddStringToObject(uptime, "unit", "seconds");
    cJSON_AddItemToArray(metrics, uptime);

    cJSON *failures = cJSON_CreateObject();
    cJSON_AddStringToObject(failures, "name", "agent.delivery.failed_cycles");
    cJSON_AddNumberToObject(failures, "value", telemetry->failed_delivery_cycles);
    cJSON_AddStringToObject(failures, "unit", "count");
    cJSON_AddItemToArray(metrics, failures);

    if (telemetry->gateway_probe_valid) {
        cJSON *rtt = cJSON_CreateObject();
        cJSON_AddStringToObject(rtt, "name", "network.gateway.rtt.ms");
        cJSON_AddNumberToObject(rtt, "value", telemetry->gateway_rtt_ms);
        cJSON_AddStringToObject(rtt, "unit", "ms");
        cJSON_AddItemToArray(metrics, rtt);

        cJSON *loss = cJSON_CreateObject();
        cJSON_AddStringToObject(loss, "name", "network.gateway.packet_loss.percent");
        cJSON_AddNumberToObject(loss, "value", telemetry->gateway_loss_percent);
        cJSON_AddStringToObject(loss, "unit", "percent");
        cJSON_AddItemToArray(metrics, loss);
    }

    if (telemetry->environment_sensor_valid) {
        cJSON *temperature = cJSON_CreateObject();
        cJSON_AddStringToObject(temperature, "name", "environment.temperature.celsius");
        cJSON_AddNumberToObject(temperature, "value", telemetry->temperature_celsius);
        cJSON_AddStringToObject(temperature, "unit", "celsius");
        cJSON_AddItemToArray(metrics, temperature);

        cJSON *humidity = cJSON_CreateObject();
        cJSON_AddStringToObject(humidity, "name", "environment.humidity.percent");
        cJSON_AddNumberToObject(humidity, "value", telemetry->humidity_percent);
        cJSON_AddStringToObject(humidity, "unit", "percent");
        cJSON_AddItemToArray(metrics, humidity);

        cJSON *pressure = cJSON_CreateObject();
        cJSON_AddStringToObject(pressure, "name", "environment.pressure.hpa");
        cJSON_AddNumberToObject(pressure, "value", telemetry->pressure_hpa);
        cJSON_AddStringToObject(pressure, "unit", "hPa");
        cJSON_AddItemToArray(metrics, pressure);
    }

    char *body = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (!body) return -1;

    char url[320];
    int result = -1;
    if (build_url(url, sizeof(url), server, "/api/v1/agents/telemetry") == 0 &&
        http_json(url, body, agent_id, credential, NULL, 0, NULL) == ESP_OK) {
        result = 0;
    }
    cJSON_free(body);
    return result;
}


int dm_cloud_claim_operation(const char *agent_id, dm_remote_operation_t *operation) {
    if (!agent_id || !operation) return -1;
    memset(operation, 0, sizeof(*operation));

    char server[256];
    char credential_id[64];
    char credential[256];
    if (
        dm_credentials_get_server(server, sizeof(server)) != 0 ||
        dm_credentials_get_agent_credential(
            credential_id,
            sizeof(credential_id),
            credential,
            sizeof(credential)
        ) != 0
    ) {
        return -1;
    }

    char url[320];
    if (build_url(url, sizeof(url), server, "/api/v1/agents/operations/claim") != 0) {
        return -1;
    }

    char response[3072] = {0};
    int status = 0;
    esp_err_t err = http_json(
        url,
        NULL,
        agent_id,
        credential,
        response,
        sizeof(response),
        &status
    );
    if (err != ESP_OK) return -1;
    if (status == 204) return 1;

    cJSON *payload = cJSON_Parse(response);
    if (!payload) return -1;
    cJSON *id = cJSON_GetObjectItemCaseSensitive(payload, "id");
    cJSON *operation_type = cJSON_GetObjectItemCaseSensitive(payload, "operationType");
    cJSON *arguments = cJSON_GetObjectItemCaseSensitive(payload, "arguments");
    int result = -1;

    if (
        cJSON_IsString(id) &&
        cJSON_IsString(operation_type) &&
        id->valuestring &&
        operation_type->valuestring &&
        strlen(id->valuestring) < sizeof(operation->id) &&
        strlen(operation_type->valuestring) < sizeof(operation->operation_type)
    ) {
        strcpy(operation->id, id->valuestring);
        strcpy(operation->operation_type, operation_type->valuestring);
        result = 0;

        if (strcmp(operation->operation_type, "firmware.update") == 0) {
            cJSON *url_value = cJSON_GetObjectItemCaseSensitive(arguments, "url");
            cJSON *sha_value = cJSON_GetObjectItemCaseSensitive(arguments, "sha256");
            cJSON *version_value = cJSON_GetObjectItemCaseSensitive(arguments, "version");
            if (
                !cJSON_IsString(url_value) ||
                !cJSON_IsString(sha_value) ||
                !cJSON_IsString(version_value) ||
                !url_value->valuestring ||
                !sha_value->valuestring ||
                !version_value->valuestring ||
                strncmp(url_value->valuestring, "https://", 8) != 0 ||
                strlen(url_value->valuestring) >= sizeof(operation->firmware_url) ||
                strlen(sha_value->valuestring) != 64 ||
                strlen(version_value->valuestring) >= sizeof(operation->firmware_version)
            ) {
                result = -1;
            } else {
                strcpy(operation->firmware_url, url_value->valuestring);
                strcpy(operation->firmware_sha256, sha_value->valuestring);
                strcpy(operation->firmware_version, version_value->valuestring);
            }
        }
    }

    cJSON_Delete(payload);
    return result;
}

int dm_cloud_complete_operation(
    const char *agent_id,
    const char *operation_id,
    int succeeded,
    const char *result_json,
    const char *error
) {
    if (!agent_id || !operation_id || strlen(operation_id) != 36) return -1;

    char server[256];
    char credential_id[64];
    char credential[256];
    if (
        dm_credentials_get_server(server, sizeof(server)) != 0 ||
        dm_credentials_get_agent_credential(
            credential_id,
            sizeof(credential_id),
            credential,
            sizeof(credential)
        ) != 0
    ) {
        return -1;
    }

    char path[128];
    int path_length = snprintf(
        path,
        sizeof(path),
        "/api/v1/agents/operations/%s/complete",
        operation_id
    );
    if (path_length <= 0 || (size_t)path_length >= sizeof(path)) return -1;

    char url[384];
    if (build_url(url, sizeof(url), server, path) != 0) return -1;

    cJSON *root = cJSON_CreateObject();
    if (!root) return -1;
    cJSON_AddStringToObject(root, "status", succeeded ? "succeeded" : "failed");

    cJSON *result = NULL;
    if (result_json && result_json[0]) {
        result = cJSON_Parse(result_json);
    }
    if (!result || !cJSON_IsObject(result)) {
        cJSON_Delete(result);
        result = cJSON_CreateObject();
    }
    cJSON_AddItemToObject(root, "result", result);
    if (!succeeded && error && error[0]) {
        cJSON_AddStringToObject(root, "error", error);
    }

    char *body = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    if (!body) return -1;
    esp_err_t err = http_json(
        url,
        body,
        agent_id,
        credential,
        NULL,
        0,
        NULL
    );
    cJSON_free(body);
    return err == ESP_OK ? 0 : -1;
}
