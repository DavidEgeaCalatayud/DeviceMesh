# DeviceMesh Agent Protocol v1

Protocol v1 is a JSON message contract for heartbeats, telemetry, events and limited safe commands. Every message carries `protocolVersion: 1` and an explicit type discriminator.

The authoritative machine-readable contracts are under `/protocol/schemas`. Implementations must pass the shared fixtures before release.
