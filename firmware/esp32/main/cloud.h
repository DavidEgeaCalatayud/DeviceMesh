#pragma once

#include "telemetry.h"

int dm_cloud_enroll_if_needed(const char *agent_id);
int dm_cloud_send_heartbeat(const char *agent_id, const dm_telemetry_t *telemetry);
int dm_cloud_send_telemetry(const char *agent_id, const dm_telemetry_t *telemetry);
