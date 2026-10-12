#pragma once

int dm_wifi_init(void);
int dm_wifi_wait_connected(unsigned timeout_ms);
int dm_wifi_rssi(void);
