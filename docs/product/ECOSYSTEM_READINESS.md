# DeviceMesh ecosystem readiness

DeviceMesh has two separate readiness concepts.

**Software readiness** means the implementation, contracts, storage, security boundaries,
operator surfaces and reproducible acceptance tooling exist in `main`. **External acceptance**
means a result that cannot be fabricated by an ordinary CI run has actually happened and its
evidence has been retained.

The machine-readable view is `GET /api/v1/system/ecosystem`; the web console exposes the same
model at **Ecosystem**.

## Software-complete components

The readiness registry covers the backend/API, web console, NMS/Syslog, Windows/Linux/macOS
agents, distributed probes, Android, iOS and ESP32. Runtime counts show devices, agents,
synthetic monitors/probes, NMS targets, push subscriptions, open incidents and stored Syslog.

## External gates

The ecosystem remains conditionally accepted until the applicable deployment has retained:

1. capacity reports for the intended 10/100/1000-agent profiles;
2. a sustained 24-hour (optionally 48-hour) soak report;
3. signed mobile installation, provider push delivery and Play/TestFlight receipts;
4. Android and iOS BLE provisioning against the reference ESP32;
5. the ESP32 HIL matrix including sensor loss/recovery, offline queue, OTA/rollback and hardening.

This separation prevents a green compiler/build from being presented as physical or provider
acceptance.
