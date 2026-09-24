# Synthetic Monitoring Architecture

DeviceMesh models two independent but complementary availability signals.

```text
Device / agent                         Externally observed service
      |                                           |
 authenticated heartbeat                          | protocol check
      v                                           v
availability_intervals                    synthetic_probe_results
      |                                           |
      +------ Agent health            Service health ------+
```

An agent can be healthy while a service is unavailable, and a service can remain reachable while its host agent is stopped. DeviceMesh therefore never derives one signal from the other.

## Execution model

The API stores monitor definitions and accepts observations. A probe process retrieves enabled monitor definitions, executes protocol-native checks and submits results. API workers do not perform outbound synthetic checks in request handlers.

V1.2 protocols:

- HTTP(S): bounded GET request, redirects disabled, expected status range.
- TCP: bounded TCP connect to explicit host and port.
- ICMP: one bounded echo request through a platform adapter. The adapter is invoked with structured arguments, not through a shell.

## Result semantics

Every execution creates an immutable observation containing:

- monitor id
- probe id
- observation timestamp
- success/failure
- latency in milliseconds when measurable
- HTTP status when applicable
- normalized failure reason

Availability summaries are calculated from the sequence of observations inside the requested window. The monitored period starts with the first observation in that window (or the latest preceding observation when available) and each observation owns the state until the next observation. The current state owns the interval up to query time.

Maintenance windows do not delete synthetic observations. They only affect alert/notification semantics.

## Security

Synthetic targets are privileged operator configuration. Validation rejects unsupported schemes, malformed hosts, invalid ports and unbounded timeouts. HTTP redirects remain disabled in V1.2. The probe contains no generic shell-command endpoint and monitor definitions cannot contain executable command text.
