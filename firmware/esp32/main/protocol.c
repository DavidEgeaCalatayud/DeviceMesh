#include "protocol.h"
#include <stdio.h>

int dm_build_heartbeat(char *buffer, size_t capacity, const char *agent_id, const char *timestamp) {
    if (!buffer || !agent_id || !timestamp || capacity == 0) return -1;
    int written = snprintf(buffer, capacity, "{\"type\":\"heartbeat\",\"protocolVersion\":%d,\"agentId\":\"%s\",\"timestamp\":\"%s\"}", DEVICEMESH_PROTOCOL_VERSION, agent_id, timestamp);
    return (written < 0 || (size_t)written >= capacity) ? -1 : written;
}
