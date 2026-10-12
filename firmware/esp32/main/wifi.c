#include "wifi.h"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#define CONNECTED_BIT BIT0

static const char *TAG = "dm_wifi";
static EventGroupHandle_t s_events;
static esp_timer_handle_t s_reconnect_timer;
static unsigned s_retry_count;
static bool s_prepared;
static bool s_started;

static void reconnect_timer_callback(void *arg) {
    (void)arg;
    esp_wifi_connect();
}

static void schedule_reconnect(void) {
    unsigned exponent = s_retry_count < 5 ? s_retry_count : 5;
    uint64_t delay_us = (uint64_t)(1U << exponent) * 1000000ULL;
    s_retry_count++;
    ESP_LOGW(TAG, "Wi-Fi disconnected; reconnect in %llus", delay_us / 1000000ULL);
    esp_timer_stop(s_reconnect_timer);
    esp_timer_start_once(s_reconnect_timer, delay_us);
}

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
        schedule_reconnect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        s_retry_count = 0;
        esp_timer_stop(s_reconnect_timer);
        xEventGroupSetBits(s_events, CONNECTED_BIT);
    }
}

int dm_wifi_prepare(void) {
    if (s_prepared) return 0;

    s_events = xEventGroupCreate();
    if (!s_events) return -1;
    if (esp_netif_init() != ESP_OK) return -1;
    esp_err_t loop_err = esp_event_loop_create_default();
    if (loop_err != ESP_OK && loop_err != ESP_ERR_INVALID_STATE) return -1;
    if (!esp_netif_create_default_wifi_sta()) return -1;

    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    if (esp_wifi_init(&config) != ESP_OK) return -1;
    if (esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &on_wifi_event, NULL) != ESP_OK) {
        return -1;
    }
    if (esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &on_wifi_event, NULL) != ESP_OK) {
        return -1;
    }

    esp_timer_create_args_t timer_args = {
        .callback = reconnect_timer_callback,
        .arg = NULL,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "dm_wifi_retry",
        .skip_unhandled_events = true,
    };
    if (esp_timer_create(&timer_args, &s_reconnect_timer) != ESP_OK) return -1;
    s_prepared = true;
    return 0;
}

int dm_wifi_init(void) {
    if (dm_wifi_prepare() != 0) return -1;
    if (s_started) return 0;
    if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK) return -1;
    if (esp_wifi_start() != ESP_OK) return -1;
    s_started = true;
    return 0;
}

int dm_wifi_wait_connected(unsigned timeout_ms) {
    if (!s_events) return -1;
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
