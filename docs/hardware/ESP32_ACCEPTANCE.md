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
