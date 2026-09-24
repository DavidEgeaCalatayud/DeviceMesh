# DeviceMesh Roadmap

## Delivered core
- FastAPI API and PostgreSQL persistence
- LAN discovery and stable device identity model
- Windows and Linux agent enrollment, heartbeat, host telemetry and controlled operations
- Web dashboard, realtime state and event timeline
- metric history, network diagnostics, threshold alerts and maintenance windows
- service inventory and observed topology
- agent SLA/outage history and telemetry retention rollups
- synthetic HTTP/TCP monitoring with service SLA
- distributed probes, multi-vantage consensus and service incidents/MTTR
- Docker Compose deployment and multi-platform CI/security gates

## Current — host platform expansion
- native Swift macOS host agent
- Keychain-backed credential persistence
- launchd operation
- parity for portable CPU/RAM/disk/network/uptime telemetry

## Next — production hardening
- clean-host end-to-end acceptance
- exercised backup/restore and disaster-recovery runbook
- 10/100/1,000-device performance baseline
- production installation bundles and signed agent artifacts
- users, sessions, RBAC and global audit
- Prometheus metrics, structured logs and Grafana dashboards

## V2 — Mobile and operations
- Android dashboard, incidents and alert client
- push notifications and offline cache
- advanced operations
- richer network topology and diagnostics

## V3 — Edge / NMS
- ESP32 probe, BLE provisioning and sensor telemetry
- SNMP, interfaces and LLDP-derived topology

## V4 — iOS
- full SwiftUI client, APNs and BLE provisioning

## V5 — Intelligence
- SLO/error budgets and richer incident management
- baselines, anomaly detection and correlation/RCA
- OpenTelemetry and production-scale observability
