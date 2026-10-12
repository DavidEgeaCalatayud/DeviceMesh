#pragma once

#include <stddef.h>

#include "telemetry.h"

typedef struct {
    char id[37];
    char operation_type[64];
    char firmware_url[2049];
    char firmware_sha256[65];
    char firmware_version[65];
} dm_remote_operation_t;

int dm_cloud_enroll_if_needed(const char *agent_id);
int dm_cloud_send_heartbeat(const char *agent_id, const dm_telemetry_t *telemetry);
int dm_cloud_send_telemetry(const char *agent_id, const dm_telemetry_t *telemetry);
int dm_cloud_claim_operation(const char *agent_id, dm_remote_operation_t *operation);
int dm_cloud_complete_operation(
    const char *agent_id,
    const char *operation_id,
    int succeeded,
    const char *result_json,
    const char *error
);
