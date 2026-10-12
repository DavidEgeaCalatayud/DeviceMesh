#include "wifi.h"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#define CONNECTED_BIT BIT0

static const char *TAG = "dm_wifi";
static EventGroupHandle_t s_events;
static unsigned s_retry_count;

static void on_wifi_event(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data
) {
    (void)arg;
    (void)event_data;
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_events, CONNECTED_BIT);
        unsigned seconds = 1U << (s_retry_count < 5 ? s_retry_count : 5);
        s_retry_count++;
        ESP_LOGW(TAG, "Wi-Fi disconnected; reconnect in %us", seconds);
        vTaskDelay(pdMS_TO_TICKS(seconds * 1000U));
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        s_retry_count = 0;
        xEventGroupSetBits(s_events, CONNECTED_BIT);
    }
}

int dm_wifi_init(void) {
    s_events = xEventGroupCreate();
    if (!s_events) return -1;
    if (esp_netif_init() != ESP_OK) return -1;
    if (esp_event_loop_create_default() != ESP_OK) return -1;
    if (!esp_netif_create_default_wifi_sta()) return -1;

    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    if (esp_wifi_init(&config) != ESP_OK) return -1;
    if (esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &on_wifi_event, NULL) != ESP_OK) {
        return -1;
    }
    if (esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &on_wifi_event, NULL) != ESP_OK) {
        return -1;
    }
    if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK) return -1;
    return esp_wifi_start() == ESP_OK ? 0 : -1;
}

int dm_wifi_wait_connected(unsigned timeout_ms) {
    EventBits_t bits = xEventGroupWaitBits(
        s_events,
        CONNECTED_BIT,
        pdFALSE,
        pdTRUE,
        pdMS_TO_TICKS(timeout_ms)
    );
    return (bits & CONNECTED_BIT) ? 0 : -1;
}

int dm_wifi_rssi(void) {
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) != ESP_OK) return -127;
    return ap.rssi;
}
