# ESP32 physical acceptance checklist

Use this checklist for each hardware revision that DeviceMesh intends to call production-ready.
Record board model/revision, ESP-IDF version, firmware commit, binary SHA-256, test date and
operator.

## Required setup

- two reference ESP32 boards of the target revision;
- one supported BME280 breakout when environmental telemetry is claimed;
- a Wi-Fi network where AP loss/recovery can be controlled;
- a production-like DeviceMesh server over trusted HTTPS;
- Android and iOS provisioning clients;
- USB serial access for recovery;
- a signed OTA test image plus a deliberately invalid image/digest.

## Acceptance cases

### Identity and provisioning

- Factory-fresh device exposes only the expected `DM-*` provisioning service.
- Wrong proof-of-possession cannot complete the secure session.
- Android provisioning succeeds end-to-end.
- iOS provisioning succeeds end-to-end.
- Enrollment token is one-use and is absent after successful enrollment.
- Reboot preserves the same DeviceMesh identity and agent credential.

### Connectivity and offline behaviour

- Wi-Fi loss does not reset the device or block the watchdog.
- Reconnect backoff increases and later recovers automatically.
- At least 30 minutes offline queues telemetry without unbounded growth.
- Queue overflow drops oldest data deterministically.
- Reconnect flushes queued samples in timestamp order before current telemetry.
- Default-gateway RTT/loss changes when controlled packet loss is introduced.

### Sensors

- With BME280 connected, temperature/humidity/pressure are plausible and update.
- Disconnecting the sensor causes metrics to become unavailable, not zero/fabricated.
- Reconnecting the sensor recovers without reflashing.

### Recovery

- Holding the recovery GPIO for three seconds clears Wi-Fi and DeviceMesh credentials.
- Stable hardware identity survives recovery.
- Device returns to BLE provisioning and can be enrolled again.

### OTA/rollback

- Valid signed image + correct SHA-256 installs into the inactive slot and reboots.
- Wrong SHA-256 is rejected without changing the boot partition.
- TLS/certificate failure aborts the update.
- A deliberately unhealthy pending image rolls back to the previous slot.
- A healthy pending image is marked valid only after a successful DeviceMesh cloud cycle.

### Hardening

On production samples:

- flash encryption is enabled;
- Secure Boot is enabled;
- `CONFIG_DM_REQUIRE_HARDENING=y`;
- an unhardened board fails closed before credentials are used;
- serial logs contain no provisioning PoP, agent credential, Wi-Fi passphrase or enrollment token;
- firmware signed by an untrusted key does not boot.

### Soak

Run at least 24 hours with heartbeat/telemetry enabled and retain:

- reset/watchdog count;
- minimum free heap and trend;
- offline queue high-water mark;
- heartbeat/telemetry failure count;
- Wi-Fi reconnect count;
- server-side p95/p99 ingest latency for this device class.

## Pass criteria

The hardware revision is accepted only when every required case has an attached result and no
unexplained reset, credential leak, unbounded queue/storage growth or failed rollback occurred.

CI build success does not satisfy this checklist. Roadmap #48/#28 should remain open until this
evidence exists for the actual board revision being shipped.


## Automated HIL smoke

A self-hosted GitHub runner with labels `self-hosted, linux, devicemesh-esp32` can execute the
`ESP32 Hardware Acceptance` workflow. The fixture must expose a supported ESP32 serial port and
have ESP-IDF available through `IDF_PATH`.

Repository secrets:

- `DEVICEMESH_HIL_BASE_URL`: HTTPS URL of the isolated DeviceMesh acceptance deployment.
- `DEVICEMESH_HIL_OPERATOR_TOKEN`: operator credential for that isolated environment.

The workflow builds and flashes the selected target, resets the board twice, verifies that the
persistent DeviceMesh UUID is identical after both boots, waits until the backend observes that
agent, and requires real Wi-Fi RSSI, free-heap, uptime, gateway RTT and packet-loss metrics. It
also fails if provisioning PoP material appears in captured serial logs.

Set `require_environment=true` when the reference fixture includes BME280; the evidence then
requires real temperature, humidity and pressure metrics. Set `require_hardening=true` only on
a manufacturing sample with Secure Boot and flash encryption provisioned; the workflow enables
the fail-closed firmware gate and requires the runtime hardening verification marker. Each run
retains a uniquely named `esp32-hardware-acceptance-<run-id>` artifact for 30 days.

This smoke is necessary but not sufficient for #28/#48. A release candidate still needs the
manual matrix above for BLE provisioning from both mobile platforms, long offline buffering,
sensor disconnect/recovery, recovery button, valid/invalid OTA, rollback and hardened eFuse
configuration.
