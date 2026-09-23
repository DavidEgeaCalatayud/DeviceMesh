# Network Probe operations

The DeviceMesh network probe is designed for networks explicitly controlled by the operator. Discovery and service checks are opt-in and bounded by configuration.

## Required discovery scope

The probe refuses to run unless at least one CIDR is explicitly configured:

```bash
export DEVICEMESH_PROBE_SCOPES="192.168.1.0/24"
```

A requested `--scope` must be contained by one of those configured networks. V1 accepts IPv4 scopes only and rejects scopes larger than 4096 addresses.

## Network quality sampling

A host that answers discovery is sampled with four bounded ICMP echo attempts. DeviceMesh records:

- `network.latency.ms`: mean RTT across successful attempts;
- `network.jitter.ms`: mean absolute difference between consecutive successful RTTs;
- `network.packet_loss.percent`: unsuccessful attempts divided by four, expressed as percentage.

If exactly one attempt succeeds, packet loss and latency are still measurable but jitter remains unknown. A host with no successful attempts is not published as reachable. These extra attempts are only sent to addresses already selected from the authorized CIDR scope; they do not expand discovery to another network.

## Optional TCP service inventory

Service discovery is disabled by default. Enable only the TCP ports you want DeviceMesh to check:

```bash
export DEVICEMESH_PROBE_TCP_PORTS="22,80,443,445,3389"
```

The allowlist is limited to 32 ports. The probe performs only a TCP connect check. It does not retrieve banners, attempt authentication, send application payloads or expand the configured port range.

Example:

```bash
export DEVICEMESH_SERVER_URL="http://localhost:8000"
export DEVICEMESH_PROBE_SOURCE="home-lan-probe"
export DEVICEMESH_PROBE_SCOPES="192.168.1.0/24"
export DEVICEMESH_PROBE_TCP_PORTS="22,80,443,445,3389"

python -m devicemesh_probe \
  --scope 192.168.1.0/24 \
  --workers 32 \
  --timeout 1.0 \
  --service-timeout 0.25
```

## Service lifecycle semantics

Each reachable host observation contains the exact set of configured ports checked in that run. The backend treats that as a complete snapshot only when at least one configured TCP port was scanned.

- a newly observed open endpoint emits `SERVICE_EXPOSED`;
- an unchanged open endpoint only refreshes `last_seen`;
- a previously open endpoint missing from a later complete snapshot emits `SERVICE_CLOSED` once;
- a closed endpoint seen open again emits `SERVICE_EXPOSED` again.

This prevents retries of the same snapshot from creating duplicate lifecycle events.

## Topology semantics

The V1 topology is intentionally **approximate**. DeviceMesh groups each device under the CIDR from its most recent probe observation. It does not claim to know physical switch ports, VLAN trunks, Wi-Fi association paths or L2 forwarding relationships.

The API exposes this explicitly as:

```json
{
  "method": "observation-segment",
  "approximate": true
}
```

Future topology adapters can add higher-confidence evidence without changing the current contract.
