# DeviceMesh V1.2 — Operator Console and Synthetic Monitoring

## Goal

Separate **agent/host availability** from **service availability** and expose the existing maintenance/remote-operation controls through an operator-facing console.

DeviceMesh should be able to answer two independent questions:

1. **Agent health** — is the managed device and its DeviceMesh agent reachable?
2. **Service health** — is a declared HTTP/TCP/ICMP target reachable from an external probe, and how well is it responding?

A service can therefore be unhealthy while its host remains healthy, and a host outage does not silently become an application-SLA datapoint.

## Operator Console

The web UI will expose the safe APIs introduced in V1.1:

- create/cancel device-scoped maintenance windows;
- view whether an alert is currently silenced by maintenance;
- queue only the declarative remote operations `telemetry.collect`, `inventory.refresh`, and `agent.health_check`;
- display operation lifecycle, timestamps, result and error;
- display audit/event history without introducing arbitrary command input.

## Synthetic Monitoring model

### Synthetic monitor

A persisted monitor defines:

- `name`;
- optional associated `device_id`;
- kind: `http`, `tcp`, or `icmp`;
- target host/URL and optional TCP port;
- interval and timeout;
- enabled state;
- HTTP expectation when applicable (method and expected status code).

### Synthetic check result

Each execution persists an immutable result:

- monitor id;
- execution timestamp;
- success/failure;
- latency in milliseconds;
- HTTP status when applicable;
- bounded error classification/message;
- probe identity.

### Service availability

Service SLA is computed from persisted synthetic checks and is intentionally separate from the host availability interval model.

Initial windows:

- 24 hours;
- 7 days;
- 30 days.

For each window expose:

- total checks;
- successful checks;
- failed checks;
- availability percentage;
- mean latency;
- p95 latency;
- current consecutive-failure duration/count where data permits.

## Probe execution

V1.2 ships a backend-managed probe worker suitable for a single DeviceMesh deployment. The executor:

- claims due monitors;
- performs bounded network I/O;
- persists results;
- schedules the next run;
- never executes target-provided code;
- never follows a monitor into shell/process execution.

HTTP probes use explicit timeouts and a bounded response body policy. TCP probes only attempt a connection. ICMP is capability/platform dependent and must fail as `unsupported` rather than escalating privileges dynamically.

## Security boundary

Synthetic targets are operator-controlled network destinations and therefore SSRF-sensitive. V1.2 must:

- reject loopback, link-local, multicast and unspecified destinations by default;
- resolve DNS and validate every resolved address before connecting;
- reject embedded credentials in HTTP URLs;
- restrict schemes to `http`/`https`;
- bound timeout, frequency and result/error sizes;
- keep ICMP privilege requirements explicit;
- preserve the existing no-arbitrary-command boundary for remote operations.

A later version can add explicit allowlisted private-network scopes for deployments that intentionally monitor internal services.

## Acceptance criteria

- host SLA and service SLA are represented by different domain models and endpoints;
- operator UI can create/cancel maintenance without raw API calls;
- operator UI can queue only allowlisted V1.1 remote operations and inspect history/results;
- HTTP and TCP synthetic checks persist latency and success/failure results;
- ICMP has an explicit supported/unsupported execution path;
- 24h/7d/30d synthetic availability summaries are queryable;
- synthetic monitor targets pass SSRF/network-boundary validation;
- disabled monitors are not executed;
- backend, web, integration and security CI remain green.
