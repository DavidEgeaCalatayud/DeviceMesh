# Synthetic monitoring

DeviceMesh synthetic monitoring supports five monitor kinds:

| Kind | Execution | Notes |
| --- | --- | --- |
| `http` | backend-local or distributed probe | GET/HEAD, expected status, TLS verification for HTTPS |
| `tcp` | backend-local or distributed probe | TCP connect latency on an explicit port |
| `dns` | backend-local or distributed probe | Resolves the target and records lookup latency |
| `tls` | backend-local or distributed probe | Validates the certificate chain and hostname; defaults to port 443 |
| `icmp` | distributed probe | Executes one bounded system `ping`; the runtime must provide an unprivileged/capability-enabled ping binary |

## Network boundary

Synthetic targets are resolved before connection. Loopback, link-local, multicast, unspecified and reserved addresses are rejected. This boundary applies after DNS resolution as well as to literal IP targets, preventing a public hostname from being used to pivot checks to prohibited addresses.

HTTP monitors reject embedded URL credentials. Authentication material must not be embedded in targets.

## Distributed probe runtime

The official probe container includes `iputils-ping` and CA certificates while continuing to run as the unprivileged `probe` user. On hosts where unprivileged ICMP is disabled, grant only the minimum platform capability required for `ping`; do not run the entire probe as root.

Probe results are stored in the durable SQLite outbox before delivery. Failed server delivery therefore does not discard completed synthetic results.

## Failure classification

Results use bounded error categories suitable for alerting and incident correlation:

- `dns` — resolution failed.
- `tls` — certificate or TLS handshake validation failed.
- `timeout` — the total check deadline elapsed.
- `connection` — connect/ICMP execution failed.
- `http_status` — HTTP returned a status other than the configured expected status.
- `policy` — the target violated the network safety policy or monitor definition.
- `unsupported` — the requested capability is unavailable in that runtime.
- `internal` — an unexpected bounded probe failure.

## Capability assignment

A distributed probe advertises the monitor kinds it is allowed to execute. Probe-to-monitor assignment remains capability checked by the server, so adding DNS/TLS support does not silently enable those checks on existing probes.

## Operational guidance

Use HTTP for application health, TCP for transport reachability, DNS for resolver visibility, TLS for certificate/hostname validation and ICMP for network reachability. For external availability decisions, assign the same monitor to multiple probe locations and consume the existing consensus/incident pipeline rather than relying on a single probe result.
