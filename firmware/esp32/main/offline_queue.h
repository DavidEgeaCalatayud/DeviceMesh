#pragma once

#include "telemetry.h"

int dm_offline_queue_init(void);
int dm_offline_queue_push(const dm_telemetry_t *sample);
int dm_offline_queue_peek(dm_telemetry_t *sample);
int dm_offline_queue_pop(void);
unsigned dm_offline_queue_count(void);
