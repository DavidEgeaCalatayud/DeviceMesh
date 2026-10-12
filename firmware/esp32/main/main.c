#include <stdint.h>

#include "ble.h"
#include "cloud.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "identity.h"
#include "nvs_flash.h"
#include "sensors.h"
#include "time_sync.h"
#include "wifi.h"

static const char *TAG = "devicemesh";

static int init_nvs(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        if (nvs_flash_erase() != ESP_OK) return -1;
        err = nvs_flash_init();
    }
    return err == ESP_OK ? 0 : -1;
}

void app_main(void) {
    if (init_nvs() != 0 || dm_identity_init() != 0) {
        ESP_LOGE(TAG, "Unable to initialize persistent identity");
        return;
    }

    char agent_id[37];
    if (dm_identity_get(agent_id, sizeof(agent_id)) != 0) return;
    ESP_LOGI(TAG, "DeviceMesh ESP32 agent %s", agent_id);

    if (dm_wifi_prepare() != 0) {
        ESP_LOGE(TAG, "Unable to initialize Wi-Fi stack");
        return;
    }

    int provisioning = dm_ble_init(agent_id);
    if (provisioning < 0) {
        ESP_LOGE(TAG, "BLE provisioning initialization failed");
        return;
    }
    if (provisioning > 0) {
        ESP_LOGI(TAG, "Awaiting secure BLE Wi-Fi provisioning");
        return;
    }

    if (dm_wifi_init() != 0 || dm_wifi_wait_connected(60000) != 0) {
        ESP_LOGE(TAG, "Wi-Fi connection unavailable");
        return;
    }

    if (dm_time_sync(30000) != 0) {
        ESP_LOGW(TAG, "SNTP synchronization not ready; cloud loop will retry");
    }

    esp_task_wdt_add(NULL);
    uint32_t failed_cycles = 0;
    for (;;) {
        esp_task_wdt_reset();

        if (dm_cloud_enroll_if_needed(agent_id) == 0) {
            dm_telemetry_t telemetry = {.failed_delivery_cycles = failed_cycles};
            if (dm_read_sensors(&telemetry) == 0 &&
                dm_cloud_send_heartbeat(agent_id, &telemetry) == 0 &&
                dm_cloud_send_telemetry(agent_id, &telemetry) == 0) {
                failed_cycles = 0;
            } else if (failed_cycles < UINT32_MAX) {
                failed_cycles++;
            }
        } else if (failed_cycles < UINT32_MAX) {
            failed_cycles++;
        }

        vTaskDelay(pdMS_TO_TICKS(30000));
    }
}
