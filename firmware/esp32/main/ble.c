#include "ble.h"

#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "wifi_provisioning/manager.h"
#include "wifi_provisioning/scheme_ble.h"

static const char *TAG = "dm_provisioning";

int dm_ble_init(const char *device_id) {
    if (!device_id || strlen(device_id) < 8) return -1;

    wifi_prov_mgr_config_t config = {
        .scheme = wifi_prov_scheme_ble,
        .scheme_event_handler = WIFI_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM,
    };
    if (wifi_prov_mgr_init(config) != ESP_OK) return -1;

    bool provisioned = false;
    if (wifi_prov_mgr_is_provisioned(&provisioned) != ESP_OK) return -1;
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

    esp_err_t err = wifi_prov_mgr_start_provisioning(
        WIFI_PROV_SECURITY_1,
        pop,
        service_name,
        NULL
    );
    return err == ESP_OK ? 1 : -1;
}
