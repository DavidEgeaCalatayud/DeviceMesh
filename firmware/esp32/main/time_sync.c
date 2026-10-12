#include "time_sync.h"

#include <time.h>

#include "esp_netif_sntp.h"
#include "freertos/FreeRTOS.h"

int dm_time_sync(unsigned timeout_ms) {
    time_t now = time(NULL);
    if (now >= 1704067200) return 0;

    esp_sntp_config_t config = ESP_NETIF_SNTP_DEFAULT_CONFIG("pool.ntp.org");
    if (esp_netif_sntp_init(&config) != ESP_OK) return -1;
    esp_err_t result = esp_netif_sntp_sync_wait(pdMS_TO_TICKS(timeout_ms));
    return result == ESP_OK ? 0 : -1;
}
