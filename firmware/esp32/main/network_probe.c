#include "network_probe.h"

#include <string.h>

#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "lwip/ip_addr.h"
#include "ping/ping_sock.h"

#define PROBE_DONE_BIT BIT0

typedef struct {
    EventGroupHandle_t events;
    uint32_t replies;
    uint32_t rtt_sum_ms;
} probe_state_t;

static void on_ping_success(esp_ping_handle_t handle, void *args) {
    probe_state_t *state = (probe_state_t *)args;
    uint32_t elapsed = 0;
    if (esp_ping_get_profile(
            handle,
            ESP_PING_PROF_TIMEGAP,
            &elapsed,
            sizeof(elapsed)
        ) == ESP_OK) {
        state->replies++;
        state->rtt_sum_ms += elapsed;
    }
}

static void on_ping_timeout(esp_ping_handle_t handle, void *args) {
    (void)handle;
    (void)args;
}

static void on_ping_end(esp_ping_handle_t handle, void *args) {
    (void)handle;
    probe_state_t *state = (probe_state_t *)args;
    xEventGroupSetBits(state->events, PROBE_DONE_BIT);
}

int dm_network_probe_gateway(dm_telemetry_t *telemetry) {
    if (!telemetry) return -1;

    esp_netif_t *netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (!netif) return -1;

    esp_netif_ip_info_t info;
    if (esp_netif_get_ip_info(netif, &info) != ESP_OK || info.gw.addr == 0) return -1;

    probe_state_t state = {
        .events = xEventGroupCreate(),
        .replies = 0,
        .rtt_sum_ms = 0,
    };
    if (!state.events) return -1;

    ip_addr_t target;
    memset(&target, 0, sizeof(target));
    IP_SET_TYPE_VAL(target, IPADDR_TYPE_V4);
    ip4_addr_set_u32(ip_2_ip4(&target), info.gw.addr);

    esp_ping_config_t config = ESP_PING_DEFAULT_CONFIG();
    config.target_addr = target;
    config.count = 3;
    config.interval_ms = 250;
    config.timeout_ms = 1000;

    esp_ping_callbacks_t callbacks = {
        .cb_args = &state,
        .on_ping_success = on_ping_success,
        .on_ping_timeout = on_ping_timeout,
        .on_ping_end = on_ping_end,
    };
    esp_ping_handle_t ping = NULL;
    if (esp_ping_new_session(&config, &callbacks, &ping) != ESP_OK) {
        vEventGroupDelete(state.events);
        return -1;
    }
    if (esp_ping_start(ping) != ESP_OK) {
        esp_ping_delete_session(ping);
        vEventGroupDelete(state.events);
        return -1;
    }

    EventBits_t bits = xEventGroupWaitBits(
        state.events,
        PROBE_DONE_BIT,
        pdTRUE,
        pdTRUE,
        pdMS_TO_TICKS(5000)
    );
    if (!(bits & PROBE_DONE_BIT)) {
        esp_ping_stop(ping);
        esp_ping_delete_session(ping);
        vEventGroupDelete(state.events);
        return -1;
    }

    esp_ping_delete_session(ping);
    vEventGroupDelete(state.events);
    telemetry->gateway_probe_valid = true;
    telemetry->gateway_loss_percent = 100.0f * (3.0f - (float)state.replies) / 3.0f;
    telemetry->gateway_rtt_ms = state.replies
        ? (float)state.rtt_sum_ms / (float)state.replies
        : 0.0f;
    return 0;
}
