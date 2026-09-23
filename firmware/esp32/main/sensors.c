#include "sensors.h"
int dm_read_sensors(dm_telemetry_t *out) { if (!out) return -1; out->temperature_c = 0; out->humidity_percent = 0; out->wifi_rssi = 0; return 0; }
