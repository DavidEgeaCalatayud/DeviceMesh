#include "ble.h"
#include "esp_log.h"
#include "wifi.h"

static const char *TAG = "devicemesh";

void app_main(void) {
    ESP_LOGI(TAG, "DeviceMesh ESP32 probe bootstrap");
    dm_wifi_init();
    dm_ble_init();
}
