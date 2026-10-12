#include "ota.h"

#include <ctype.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_task_wdt.h"
#include "mbedtls/sha256.h"

static const char *TAG = "dm_ota";

static int hex_nibble(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    value = (char)tolower((unsigned char)value);
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    return -1;
}

static int decode_sha256(const char *hex, uint8_t out[32]) {
    if (!hex || strlen(hex) != 64) return -1;
    for (size_t index = 0; index < 32; index++) {
        int high = hex_nibble(hex[index * 2]);
        int low = hex_nibble(hex[index * 2 + 1]);
        if (high < 0 || low < 0) return -1;
        out[index] = (uint8_t)((high << 4) | low);
    }
    return 0;
}

int dm_ota_apply(const char *url, const char *expected_sha256) {
    if (!url || strncmp(url, "https://", 8) != 0 || strlen(url) > 2048) return -1;

    uint8_t expected[32];
    if (decode_sha256(expected_sha256, expected) != 0) return -1;

    esp_http_client_config_t config = {
        .url = url,
        .timeout_ms = 30000,
        .keep_alive_enable = true,
        .crt_bundle_attach = esp_crt_bundle_attach,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return -1;

    int result = -1;
    esp_ota_handle_t ota = 0;
    bool ota_started = false;
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);

    if (esp_http_client_open(client, 0) != ESP_OK) goto cleanup;
    (void)esp_http_client_fetch_headers(client);
    if (esp_http_client_get_status_code(client) != 200) goto cleanup;

    const esp_partition_t *partition = esp_ota_get_next_update_partition(NULL);
    if (!partition) goto cleanup;
    if (esp_ota_begin(partition, OTA_SIZE_UNKNOWN, &ota) != ESP_OK) goto cleanup;
    ota_started = true;

    if (mbedtls_sha256_starts(&sha, 0) != 0) goto cleanup;

    uint8_t buffer[4096];
    int read = 0;
    while ((read = esp_http_client_read(client, (char *)buffer, sizeof(buffer))) > 0) {
        if (mbedtls_sha256_update(&sha, buffer, (size_t)read) != 0) goto cleanup;
        if (esp_ota_write(ota, buffer, (size_t)read) != ESP_OK) goto cleanup;
        esp_task_wdt_reset();
    }
    if (read < 0 || !esp_http_client_is_complete_data_received(client)) goto cleanup;

    uint8_t actual[32];
    if (mbedtls_sha256_finish(&sha, actual) != 0) goto cleanup;
    if (memcmp(expected, actual, sizeof(actual)) != 0) {
        ESP_LOGE(TAG, "Downloaded firmware SHA-256 does not match the approved digest");
        goto cleanup;
    }

    if (esp_ota_end(ota) != ESP_OK) {
        ota_started = false;
        goto cleanup;
    }
    ota_started = false;
    if (esp_ota_set_boot_partition(partition) != ESP_OK) goto cleanup;

    ESP_LOGI(TAG, "OTA image validated and scheduled for next boot");
    result = 0;

cleanup:
    if (ota_started) esp_ota_abort(ota);
    mbedtls_sha256_free(&sha);
    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    return result;
}

int dm_ota_confirm_running_image(void) {
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (!running) return -1;

    esp_ota_img_states_t state;
    esp_err_t err = esp_ota_get_state_partition(running, &state);
    if (err == ESP_ERR_NOT_SUPPORTED) return 0;
    if (err != ESP_OK) return -1;
    if (state != ESP_OTA_IMG_PENDING_VERIFY) return 0;

    err = esp_ota_mark_app_valid_cancel_rollback();
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Running OTA image confirmed after successful cloud health cycle");
        return 0;
    }
    return -1;
}

int dm_ota_cancel_pending_update(void) {
    const esp_partition_t *running = esp_ota_get_running_partition();
    if (!running) return -1;
    return esp_ota_set_boot_partition(running) == ESP_OK ? 0 : -1;
}
