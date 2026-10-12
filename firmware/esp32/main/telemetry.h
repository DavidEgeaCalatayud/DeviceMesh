#pragma once

#include <stdint.h>

typedef struct {
    int wifi_rssi;
    uint32_t free_heap_bytes;
    uint64_t uptime_seconds;
    uint32_t failed_delivery_cycles;
} dm_telemetry_t;
