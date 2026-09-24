# DeviceMesh Network & Synthetic Probe

The probe is the external data-plane process for DeviceMesh. It has two independent modes:

- **bounded LAN discovery** for explicitly allowlisted CIDR scopes;
- **synthetic monitoring** for operator-defined HTTP(S), TCP and ICMP monitors.

The API remains the control plane. Synthetic checks are never executed inside API request handlers.

## Install

```bash
cd agents/probe
python -m pip install -e .
```

For development/test tooling:

```bash
python -m pip install -e ".[dev]"
```

## Synthetic monitoring

Configure a probe identity, the DeviceMesh API and the dedicated probe credential:

```bash
export DEVICEMESH_SERVER_URL=http://localhost:8000
export DEVICEMESH_PROBE_ID=probe-local
export DEVICEMESH_PROBE_TOKEN=replace-with-a-dedicated-probe-token
```

Execute every enabled monitor once:

```bash
devicemesh-probe synthetics --once
```

Run continuously while respecting each monitor's configured interval:

```bash
devicemesh-probe synthetics
```

The probe fetches only enabled monitor definitions using `Authorization: Probe …`, executes bounded protocol-native checks and publishes observations back to DeviceMesh. This credential is intentionally separate from `DEVICEMESH_OPERATOR_TOKEN`.

### Protocols

- **HTTP(S):** bounded `GET`, redirects disabled, configurable expected status range.
- **TCP:** bounded connection to one explicit host/port.
- **ICMP:** one bounded echo request through the platform `ping` utility with a fixed argument list and `shell=False`.

There is no generic command payload, shell endpoint, PowerShell/Bash bridge or arbitrary process-execution primitive.

## LAN discovery

Discovery remains explicitly scoped. Example:

```bash
export DEVICEMESH_SERVER_URL=http://localhost:8000
export DEVICEMESH_PROBE_SCOPES=192.168.1.0/24
export DEVICEMESH_PROBE_TCP_PORTS=22,80,443

devicemesh-probe --scope 192.168.1.0/24
```

A requested discovery network must be a subnet of one of the configured `DEVICEMESH_PROBE_SCOPES` entries.

## Availability semantics

Synthetic service availability is intentionally independent from agent heartbeat availability. A healthy agent can host an unavailable service and a reachable service can outlive or bypass an unavailable agent.

A probe result owns service state for a bounded coverage period. If the probe stops reporting beyond that coverage, DeviceMesh marks the monitor **stale** and excludes the unknown gap from SLA calculations instead of assuming uptime or downtime.
