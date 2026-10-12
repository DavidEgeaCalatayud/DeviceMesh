#include "operations.h"

#include <stdio.h>
#include <string.h>

#include "cloud.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "network_probe.h"
#include "offline_queue.h"
#include "ota.h"
#include "sensors.h"
#include "wifi.h"

static const char *TAG = "dm_operations";

static void complete_failure(
    const char *agent_id,
    const dm_remote_operation_t *operation,
    const char *error
) {
    if (dm_cloud_complete_operation(agent_id, operation->id, 0, "{}", error) != 0) {
        ESP_LOGW(TAG, "Unable to report failed operation %s", operation->id);
    }
}

int dm_operations_poll(const char *agent_id) {
    if (!agent_id) return -1;

    dm_remote_operation_t operation;
    int claim = dm_cloud_claim_operation(agent_id, &operation);
    if (claim != 0) return claim;

    if (strcmp(operation.operation_type, "firmware.update") == 0) {
        ESP_LOGI(TAG, "Applying approved firmware update %s", operation.firmware_version);
        if (dm_ota_apply(operation.firmware_url, operation.firmware_sha256) != 0) {
            complete_failure(
                agent_id,
                &operation,
                "firmware download, image validation or SHA-256 verification failed"
            );
            return -1;
        }
        if (
            dm_cloud_complete_operation(
                agent_id,
                operation.id,
                1,
                "{\"rebootRequired\":true,\"validated\":true}",
                NULL
            ) != 0
        ) {
            dm_ota_cancel_pending_update();
            return -1;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_restart();
        return 0;
    }

    if (strcmp(operation.operation_type, "agent.health_check") == 0) {
        char result[256];
        snprintf(
            result,
            sizeof(result),
            "{\"freeHeapBytes\":%lu,\"wifiRssi\":%d,\"offlineQueueDepth\":%u}",
            (unsigned long)esp_get_free_heap_size(),
            dm_wifi_rssi(),
            dm_offline_queue_count()
        );
        return dm_cloud_complete_operation(
            agent_id,
            operation.id,
            1,
            result,
            NULL
        );
    }

    if (strcmp(operation.operation_type, "telemetry.collect") == 0) {
        dm_telemetry_t telemetry = {0};
        dm_read_sensors(&telemetry);
        dm_network_probe_gateway(&telemetry);
        if (dm_cloud_send_telemetry(agent_id, &telemetry) == 0) {
            return dm_cloud_complete_operation(
                agent_id,
                operation.id,
                1,
                "{\"telemetrySubmitted\":true}",
                NULL
            );
        }
        complete_failure(agent_id, &operation, "telemetry submission failed");
        return -1;
    }

    if (strcmp(operation.operation_type, "inventory.refresh") == 0) {
        dm_telemetry_t telemetry = {0};
        dm_read_sensors(&telemetry);
        if (dm_cloud_send_heartbeat(agent_id, &telemetry) == 0) {
            return dm_cloud_complete_operation(
                agent_id,
                operation.id,
                1,
                "{\"heartbeatSubmitted\":true}",
                NULL
            );
        }
        complete_failure(agent_id, &operation, "inventory heartbeat failed");
        return -1;
    }

    complete_failure(agent_id, &operation, "operation unsupported by ESP32 agent");
    return -1;
}
