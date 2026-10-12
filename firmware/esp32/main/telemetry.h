#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int wifi_rssi;
    uint32_t free_heap_bytes;
    uint64_t uptime_seconds;
    int64_t sampled_at_unix;
    uint32_t failed_delivery_cycles;
    bool gateway_probe_valid;
    float gateway_rtt_ms;
    float gateway_loss_percent;
} dm_telemetry_t;
