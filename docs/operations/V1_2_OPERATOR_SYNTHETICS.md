# DeviceMesh V1.2 — Operator Console and Synthetic Monitoring

## Goal

Extend DeviceMesh beyond host/agent availability into externally observed service health while exposing the V1.1 operational controls through a safe operator UI.

## Scope

### Synthetic monitoring

- HTTP(S), TCP and ICMP monitor definitions.
- Probe results persisted as immutable observations.
- Service availability summaries for 24h / 7d / 30d over actual monitored time.
- Current service state, current outage duration, outage count, longest outage and latency aggregates.
- Clear separation between host/agent availability and externally observed service availability.
- HTTP checks support expected status ranges and bounded request timeout.
- TCP checks validate connectability to an explicit host/port.
- ICMP checks are executed by the probe process and never by the API request path.
- Probe execution is allowlisted from stored monitor definitions; no arbitrary command execution.

### Operator console

- Create/cancel maintenance windows from the web UI.
- Queue only the existing declarative remote operations: `telemetry.collect`, `inventory.refresh`, `agent.health_check`.
- Show remote-operation lifecycle/history including timestamps, result and error.
- Show maintenance/silence state without hiding telemetry or incidents.

## Security boundary

Synthetic targets are operator-managed configuration. The backend validates schemes, ports, hostnames/IPs and timeouts. The probe executes protocol-native checks only and does not expose shell, PowerShell, Bash or arbitrary process execution. HTTP redirects are disabled in V1.2 so a configured target cannot silently pivot the probe to another address.

## Definition of done

- [ ] monitor definitions and observations are persisted through Alembic migration
- [ ] HTTP/TCP/ICMP checks have unit tests
- [ ] service SLA summaries expose 24h/7d/30d availability and outages
- [ ] API supports monitor CRUD/read and probe result ingestion
- [ ] device detail distinguishes Agent health from Service health
- [ ] operator UI supports maintenance create/cancel
- [ ] operator UI supports allowlisted remote operations and audit/history
- [ ] probe CI, backend CI, web CI, integration CI and security CI are green
