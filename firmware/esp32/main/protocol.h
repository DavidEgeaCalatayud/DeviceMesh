#pragma once
#include <stddef.h>
#define DEVICEMESH_PROTOCOL_VERSION 1
int dm_build_heartbeat(char *buffer, size_t capacity, const char *agent_id, const char *timestamp);
