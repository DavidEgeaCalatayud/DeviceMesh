# DeviceMesh ESP32 Probe

DeviceMesh ESP32 uses the existing V1 agent protocol rather than a separate hardware wire
contract. The firmware is intended to behave as a small enrolled DeviceMesh agent and network
probe.

## Implemented lifecycle

1. A UUIDv4 agent identity is generated once and persisted in NVS.
2. An unprovisioned unit exposes ESP-IDF Wi-Fi Provisioning over BLE using Security 1
   proof-of-possession and the `DM-<suffix>` service name.
3. Android/iOS can send the HTTPS DeviceMesh server URL and a short-lived one-use enrollment
   token through the encrypted `devicemesh-config` endpoint while provisioning Wi-Fi.
4. On successful provisioning the device restarts automatically.
5. After Wi-Fi and SNTP are available, the unit exchanges the one-use token for a normal
   DeviceMesh agent credential, persists it and erases the enrollment token.
6. Heartbeat, telemetry and remote-operation calls use the same authenticated DeviceMesh V1
   agent surface as the desktop agents.

## Runtime behaviour

The firmware currently provides:

- bounded exponential Wi-Fi reconnect using an ESP timer rather than blocking the Wi-Fi event
  loop;
- task-watchdog participation;
- public-CA TLS validation through the ESP-IDF certificate bundle;
- heartbeat and authenticated telemetry every 30 seconds;
- Wi-Fi RSSI, free heap, uptime and delivery-failure telemetry;
- three-packet ICMP probing of the default gateway with RTT and packet-loss metrics;
- optional BME280 temperature, humidity and pressure through the managed Espressif component;
- a persistent, bounded NVS-backed telemetry queue that retains original sample timestamps,
  drops the oldest sample at capacity and drains before the current sample after recovery;
- allowlisted remote operations for health checks, telemetry collection, inventory refresh and
  firmware update;
- A/B OTA partitions, HTTPS download, exact SHA-256 validation and ESP-IDF rollback;
- confirmation of a pending OTA image only after a successful DeviceMesh cloud cycle;
- active-low recovery GPIO support that clears Wi-Fi, DeviceMesh credentials and the offline
  queue while retaining the stable hardware identity.

Environmental values are omitted when the optional BME280 profile is disabled or the sensor is
not available; DeviceMesh does not fabricate zero readings.

## Hardening

The server URL must use HTTPS and certificate verification must not be disabled. Private
DeviceMesh CAs must be compiled into the firmware trust configuration.

Development builds can leave the hardware hardening gate disabled. Manufacturing builds should
enable `CONFIG_DM_REQUIRE_HARDENING=y`, provision Secure Boot and flash encryption, and manage
the firmware signing key outside the repository. With that flag enabled, the firmware fails
closed before using DeviceMesh credentials if either protection is absent.

## Build and hardware documentation

See:

- `docs/hardware/ESP32.md` for reference hardware, BME280 wiring, build/flash, provisioning,
  OTA, recovery and troubleshooting.
- `docs/hardware/ESP32_ACCEPTANCE.md` for the physical acceptance matrix required before a
  board revision is declared production-ready.

CI compiles the firmware and host-tests pure protocol/queue logic, but CI alone does **not**
complete roadmap #28/#48. Those points require retained evidence from named physical boards,
including Android/iOS provisioning, sensor disconnect/recovery, Wi-Fi interruption, OTA rollback,
Secure Boot/flash encryption and a hardware soak.
