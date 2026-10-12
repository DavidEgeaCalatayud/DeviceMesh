# DeviceMesh ESP32 hardware operations

This guide covers the reference ESP32 deployment path for DeviceMesh hardware probes. It is
written for operators who need to buy, flash, provision, recover and validate a device without
reading the firmware source.

## Reference hardware

The firmware targets ESP-IDF-capable ESP32 boards with at least 4 MB flash, Wi-Fi and Bluetooth
LE. The current reference profile assumes:

- an ESP32/ESP32-S3 class development board with 4 MB or more flash;
- 3.3 V logic;
- optional Bosch BME280 environmental sensor over I2C;
- a momentary recovery button wired active-low to the configured recovery GPIO.

The firmware does not invent environmental values. If the BME280 profile is disabled or the
sensor is absent, temperature, humidity and pressure metrics are omitted.

### BME280 wiring

When `CONFIG_DM_BME280_ENABLED=y`, the defaults are:

| Signal | ESP32 default | BME280 |
| --- | --- | --- |
| 3V3 | 3.3 V | VIN/VCC |
| GND | GND | GND |
| SDA | GPIO 21 | SDA |
| SCL | GPIO 22 | SCL |

Use 3.3 V-compatible breakout boards. GPIOs are configurable through menuconfig.

## Build

Requirements:

- ESP-IDF matching the firmware CI image/toolchain;
- Python and the ESP-IDF Component Manager;
- USB serial access to the board.

From `firmware/esp32`:

```sh
idf.py set-target esp32
idf.py build
```

The component manager resolves the pinned DeviceMesh dependencies, including the optional
Espressif BME280 component.

For the environmental sensor profile:

```sh
idf.py menuconfig
# DeviceMesh hardware -> Enable BME280 environmental sensor
idf.py build
```

## Flash and first boot

Connect the board over USB and run:

```sh
idf.py -p /dev/ttyUSB0 flash monitor
```

Use the platform-equivalent serial device on macOS or Windows.

On first boot DeviceMesh creates a persistent UUIDv4 identity in NVS. Keep that identity stable
across normal firmware upgrades. A factory/recovery reset intentionally clears Wi-Fi and
DeviceMesh credentials while retaining this identity.

The serial log prints a BLE service named `DM-<suffix>` and a proof-of-possession value. Treat
the PoP as provisioning material: do not publish screenshots or serial logs containing it.

## Mobile provisioning

Provisioning is performed from the DeviceMesh Android or iOS client by an administrator:

1. Sign in to the DeviceMesh server over HTTPS.
2. Open **Provision hardware**.
3. Scan for the `DM-*` device.
4. Enter the proof-of-possession shown on the device/label.
5. Enter the target Wi-Fi SSID and passphrase.
6. Confirm provisioning.

The mobile client creates a short-lived, one-use agent enrollment token from DeviceMesh and sends
the HTTPS server URL plus that token through the encrypted ESP-IDF BLE Security 1 session. Wi-Fi
credentials are provisioned in the same BLE session.

After provisioning completes the device restarts automatically, joins Wi-Fi, synchronizes time,
exchanges the one-use token for a normal DeviceMesh agent credential and erases the enrollment
token.

## Normal runtime

A healthy unit performs the following loop:

- persistent identity and credential load;
- Wi-Fi reconnect with bounded exponential backoff;
- SNTP time synchronization;
- authenticated heartbeat;
- real system telemetry: Wi-Fi RSSI, free heap and uptime;
- optional BME280 temperature/humidity/pressure;
- three-packet ICMP probe against the default gateway, reporting RTT and loss;
- bounded persistent offline telemetry queue;
- remote-operation polling;
- watchdog servicing.

Queued telemetry retains its original sample timestamp and is replayed before the current sample
once cloud connectivity recovers. The queue is bounded; when full it drops the oldest sample
rather than growing flash usage without limit.

## OTA and rollback

The ESP32 partition table contains two OTA application slots and `otadata`. Firmware updates are
accepted only through the allowlisted `firmware.update` remote operation. The operation requires:

- a bounded HTTPS URL;
- an expected SHA-256 digest;
- a target version string.

The device downloads into the inactive OTA partition, hashes the exact bytes while writing and
refuses the image if the SHA-256 does not match. It switches boot partition only after validation.

ESP-IDF rollback is enabled. A newly booted image is marked valid only after a successful
DeviceMesh cloud health cycle. If the new image cannot reach that point, the bootloader can roll
back to the previous application slot.

For production, Secure Boot is the authenticity boundary: SHA-256 protects integrity against
download corruption or substitution relative to the approved operation, while Secure Boot
prevents unsigned firmware from becoming trusted code.

## Production hardening

Development builds allow hardware security to be disabled. Production/manufacturing builds must
enable `CONFIG_DM_REQUIRE_HARDENING=y` and provision:

- ESP32 Secure Boot;
- ESP32 flash encryption;
- a controlled firmware signing key lifecycle.

With `CONFIG_DM_REQUIRE_HARDENING=y`, DeviceMesh fails closed before reading persistent
credentials if either Secure Boot or flash encryption is unavailable.

Never disable TLS certificate validation. Public-CA DeviceMesh deployments use the ESP-IDF
certificate bundle. Private-CA deployments must compile the deployment CA into the firmware trust
configuration.

## Recovery

The default recovery GPIO is GPIO 27, configurable with `CONFIG_DM_RECOVERY_GPIO`.

To reset provisioning:

1. Power the unit off.
2. Hold the recovery button active-low.
3. Power on and continue holding for at least three seconds.
4. Release after the log confirms recovery.

Recovery clears:

- Wi-Fi provisioning state;
- DeviceMesh server/enrollment/agent credentials;
- the offline telemetry queue.

It retains the stable DeviceMesh hardware identity. The unit returns to BLE provisioning mode on
the next boot.

If recovery firmware itself does not boot, reflash over USB using the known-good release image
and partition table.

## Operational troubleshooting

**No `DM-*` BLE device appears:** verify Bluetooth is enabled, the board is not already Wi-Fi
provisioned, and the firmware reached provisioning mode. Use the recovery procedure if necessary.

**Provisioning succeeds but DeviceMesh never shows the device:** verify the server URL is HTTPS,
DNS/routes are reachable from the target Wi-Fi, system time can reach SNTP, and the one-use
enrollment token has not expired.

**Device repeatedly goes offline:** inspect `network.wifi.rssi.dbm`,
`network.gateway.rtt.ms`, `network.gateway.packet_loss.percent` and
`agent.delivery.failed_cycles`. A growing offline queue with good Wi-Fi usually indicates
server/TLS/routing failure rather than radio signal.

**Environmental metrics are absent:** verify the BME280 profile is enabled, GPIO wiring is
correct and the sensor uses the supported I2C address. Absence is treated as unavailable data,
not a zero reading.

**OTA does not activate:** verify the URL is HTTPS, the SHA-256 exactly matches the binary,
partition sizes fit the image and—on hardened units—the image is signed for the provisioned
Secure Boot trust root.

## Release evidence

A firmware build is not by itself physical acceptance. Before calling a hardware revision
production-ready, execute and retain the checklist in
`docs/hardware/ESP32_ACCEPTANCE.md` against named physical boards and firmware artifacts.
