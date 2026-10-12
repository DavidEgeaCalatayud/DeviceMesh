# DeviceMesh ESP32 hardware guide

This guide is the operational reference for buying, flashing, provisioning, recovering and
validating the DeviceMesh ESP32 probe.

## Reference hardware

Minimum supported reference:

- ESP32 development board supported by the ESP-IDF version used in CI.
- USB data cable and a stable 5 V supply.
- 2.4 GHz Wi-Fi with outbound HTTPS and NTP access.
- Android 8+ or iOS 17+ DeviceMesh mobile client for BLE provisioning.
- Optional BME280 temperature/humidity/pressure sensor.

Reference BME280 wiring when the firmware option is enabled:

| BME280 | ESP32 default |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

SDA/SCL are compile-time configurable through DeviceMesh hardware menuconfig. Do not connect a
5 V-only sensor bus directly to ESP32 GPIO.

## Build and flash

Install the ESP-IDF version used by Firmware CI, then:

    cd firmware/esp32
    idf.py set-target esp32
    idf.py menuconfig
    idf.py build
    idf.py -p /dev/ttyUSB0 flash monitor

Enable DeviceMesh hardware -> BME280 only when the physical sensor is present. The firmware
never fabricates environmental values when that option is disabled or the sensor cannot be read.

A first boot prints a stable UUID and a BLE service named DM-xxxxxx. Record the UUID. Its first
12 characters are the proof-of-possession used by the reference provisioning profile.

## Secure provisioning

1. Sign into DeviceMesh mobile as an administrator.
2. Open Provision and scan for DM-*.
3. Select the board.
4. Enter the proof-of-possession printed by the board and the target Wi-Fi credentials.
5. The mobile app creates a 15-minute one-use agent enrollment token.
6. The phone establishes ESP-IDF Security 1 over BLE.
7. Inside that encrypted session it writes the HTTPS DeviceMesh URL and enrollment token to
   devicemesh-config, then provisions Wi-Fi.
8. The board exchanges the one-use token for a normal DeviceMesh agent credential and erases the
   enrollment token.

The firmware rejects non-HTTPS DeviceMesh URLs. Public CA certificates are verified using the
ESP-IDF certificate bundle. A private DeviceMesh CA must be deliberately added to firmware trust;
do not disable certificate verification.

## Runtime behavior

Every 30 seconds the reference firmware:

- refreshes watchdog state;
- reads Wi-Fi RSSI, free heap and uptime;
- optionally reads a real BME280;
- sends three ICMP probes to the current default gateway and records mean RTT/loss;
- sends a DeviceMesh heartbeat;
- replays queued telemetry from NVS;
- sends the current telemetry sample.

Wi-Fi reconnect is scheduled with bounded exponential backoff rather than blocking the ESP event
loop. Up to 64 telemetry snapshots are retained in the NVS offline queue. On overflow the oldest
snapshot is replaced. Original sample timestamps are retained.

## Recovery

The reference recovery GPIO is GPIO 0, active low. It is configurable in menuconfig.

To recover a provisioned board:

1. Power-cycle the device while holding the recovery input low.
2. Keep it held for at least three seconds.
3. The firmware clears Wi-Fi settings, DeviceMesh credentials and queued telemetry.
4. The stable DeviceMesh hardware identity is retained.
5. Restart and provision again from mobile.

Recovery intentionally does not erase identity so historical device correlation remains stable.

## Diagnostics

Expected serial milestones include:

- DeviceMesh ESP32 agent <uuid>
- BLE provisioning service DM-xxxxxx on an unprovisioned device
- Wi-Fi already provisioned after provisioning
- no repeated Cloud enrollment configuration missing
- no watchdog reset under normal operation

In DeviceMesh, verify that the agent appears online and telemetry contains:

- network.wifi.rssi.dbm
- memory.free.bytes
- system.uptime.seconds
- agent.delivery.failed_cycles
- network.gateway.rtt.ms
- network.gateway.packet_loss.percent
- optional environment.temperature.celsius
- optional environment.humidity.percent
- optional environment.pressure.hpa

## Physical acceptance

A release is not hardware-qualified merely because Firmware CI compiles. Use the dedicated
self-hosted hardware acceptance workflow with an attached reference board and retain its result.

Required physical checks:

1. clean flash boots without reset loop;
2. BLE discovery and proof-of-possession session succeed from Android and iOS;
3. wrong PoP is rejected;
4. Wi-Fi provisioning succeeds;
5. one-use enrollment succeeds once and cannot be replayed;
6. heartbeat and telemetry appear in DeviceMesh;
7. gateway loss/RTT changes when connectivity is impaired;
8. disconnect Wi-Fi long enough to create offline samples, restore it and verify replay;
9. reboot and verify identity/credentials survive;
10. perform recovery and verify identity remains stable while credentials/Wi-Fi are cleared;
11. if BME280 is fitted, compare readings against a reference sensor;
12. run the board continuously for the declared hardware soak window without watchdog/reset loop.

OTA/rollback and signed firmware acceptance are still required before the firmware can be called
fully production-ready.
