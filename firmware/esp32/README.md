# DeviceMesh ESP32 Probe

The firmware uses the existing DeviceMesh V1 machine protocol rather than defining a parallel
wire contract.

## Lifecycle

1. A UUIDv4 agent identity is generated once and persisted in NVS.
2. If Wi-Fi is not provisioned, the device exposes ESP-IDF Wi-Fi Provisioning over BLE using
   proof-of-possession. The service is named DM-<device suffix>; the PoP is derived from the
   printed device identity.
3. DeviceMesh server URL and a one-use enrollment token are stored in the dm_secrets NVS
   namespace by provisioning/manufacturing tooling.
4. After Wi-Fi is available, the firmware exchanges the enrollment token for a normal DeviceMesh
   agent credential, persists that credential and erases the one-use token.
5. Heartbeats use the same Agent authorization, timestamp and nonce headers as Windows/Linux.
6. Wi-Fi reconnect uses bounded exponential backoff and the main loop is covered by the ESP-IDF
   task watchdog.

The server URL must be HTTPS. The HTTP client validates public CA certificates through the ESP-IDF
certificate bundle. Private DeviceMesh CAs must be added to firmware trust before deployment;
certificate verification must not be disabled.

## Telemetry and hardware boundary

The current firmware reads real system-level signals: Wi-Fi RSSI, uptime and free heap. It does
not fabricate temperature/humidity when no physical sensor is selected.

OTA with rollback, persistent offline telemetry buffering, environmental sensor drivers and a
named physical hardware acceptance fixture remain required before roadmap item #28 can be called
production-ready.
