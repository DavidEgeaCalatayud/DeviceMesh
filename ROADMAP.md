# DeviceMesh Roadmap

The authoritative implementation ledger is
[`docs/product/IMPLEMENTATION_57_POINTS.md`](docs/product/IMPLEMENTATION_57_POINTS.md).
This page is the compact product view.

## Delivered software

- production FastAPI/PostgreSQL/Redis platform, migrations, backup/restore and HTTPS deployment;
- service catalogue, dependencies, incidents, SLO/error budgets, notification routing, audit and
  explainable root-cause analysis;
- Windows, Linux and macOS agents with authenticated telemetry and allowlisted operations;
- distributed synthetic probes, quorum consensus and HTTP/TCP/DNS/TLS/ICMP monitoring;
- SNMPv3 NMS polling, persistent interface counters/inventory, routes, ARP, VLAN, LLDP/CDP
  physical topology and persistent correlated Syslog;
- native Android and iOS operator clients with secure sessions, push lifecycle, signed-release
  pipelines and ESP32 BLE provisioning;
- ESP32 enrolled agent/probe software with secure provisioning, telemetry, optional BME280,
  gateway probing, offline buffering, OTA/rollback, recovery and HIL tooling;
- retention/capacity tooling, Prometheus/Grafana, structured logs, HA/failure/performance
  acceptance and supply-chain provenance;
- repository hygiene automation, compatibility policies and machine-readable ecosystem
  readiness.

## External acceptance still required

These are execution/evidence gates, not missing software features:

1. retain capacity reports for the intended 10/100/1000-agent operating profiles;
2. execute and retain a sustained 24-hour soak (and 48-hour profile if that claim is required);
3. install signed mobile builds on supported physical devices, verify FCM/APNs foreground and
   background delivery, and retain Play internal/TestFlight distribution evidence;
4. validate Android and iOS BLE provisioning end-to-end against the reference ESP32;
5. execute the ESP32 HIL matrix including BME280 disconnect/recovery, offline queue, OTA/rollback,
   Secure Boot/flash encryption and the declared hardware soak.

Use `GET /api/v1/system/ecosystem` or the **Ecosystem** web page to keep software readiness
separate from these external gates.

## Explicitly deferred

- OpenTelemetry tracing (#37);
- Kubernetes/Helm until deployment scale justifies it (#41);
- desktop-agent auto-update until release-channel policy requires it (#52);
- statistical/ML anomaly detection until retained scale/soak evidence is available (#57).

No deferred item is required to claim the current local-first V1 software implementation complete.
