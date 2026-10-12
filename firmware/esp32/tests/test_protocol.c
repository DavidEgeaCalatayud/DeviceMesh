#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "protocol.h"

int main(void) {
    char buffer[256];
    int written = dm_build_heartbeat(
        buffer,
        sizeof(buffer),
        "123e4567-e89b-12d3-a456-426614174000",
        "2026-10-12T00:00:00Z"
    );
    assert(written > 0);
    assert(strstr(buffer, "\"protocolVersion\":1") != NULL);
    assert(strstr(buffer, "\"type\":\"heartbeat\"") != NULL);
    assert(dm_build_heartbeat(NULL, sizeof(buffer), "a", "b") == -1);

    char tiny[8];
    assert(dm_build_heartbeat(tiny, sizeof(tiny), "agent", "time") == -1);
    puts("protocol tests passed");
    return 0;
}
