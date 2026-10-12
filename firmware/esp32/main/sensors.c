#include "sensors.h"

#include "esp_heap_caps.h"
#include "esp_timer.h"
#include <time.h>
#include "wifi.h"

int dm_read_sensors(dm_telemetry_t *out) {
    if (!out) return -1;
    out->wifi_rssi = dm_wifi_rssi();
    out->free_heap_bytes = esp_get_free_heap_size();
    out->uptime_seconds = (uint64_t)(esp_timer_get_time() / 1000000ULL);
    out->sampled_at_unix = (int64_t)time(NULL);
    return 0;
}
