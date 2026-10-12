# Capacity, retention and soak acceptance

DeviceMesh separates short CI regression tests from long-running production evidence.

## Retention policy

The elected scheduler enforces the following default classes:

| Data class | Default | Action |
|---|---:|---|
| Raw telemetry | 7 days | Compact to hourly rollups, then delete raw samples |
| Hourly telemetry rollups | 365 days | Delete |
| Device events | 90 days | Delete |
| Synthetic check results | 90 days | Delete |
| Discovery observations | 30 days | Delete historical observations |
| NMS interface counter samples | 90 days | Delete samples; current interface inventory remains |
| Syslog | 90 days | Delete |
| Human audit log | 730 days | Delete |
| Agent/security audit events | 730 days | Delete |
| Notification delivery attempts | 90 days | Delete delivery history |

Devices, agents, current interface/service/NMS inventories, alert/incident records,
maintenance windows and configured NMS targets are retained until an explicit administrative
delete/archive lifecycle exists. This prevents a time-based job from silently deleting product
state.

## Capacity evidence

Run:

    PYTHONPATH=backend python tools/benchmarking/capacity_report.py --output artifacts/capacity.json

The report captures total PostgreSQL size, connection utilization, buffer cache hit ratio, table
live/dead tuples, table/index byte sizes and index/sequence scan counts. Capture it before and
after each scale/soak run. Capacity claims must cite these files rather than extrapolating from a
single short CI benchmark.

The current engineering objectives are:

- authenticated heartbeat/telemetry error rate <= 0.1%;
- p95 request latency <= 1000 ms under the declared test profile;
- PostgreSQL connection utilization must remain below 80%;
- no unbounded table without either a retention rule or an explicitly indefinite product-state
  classification;
- table/index growth must be reported for 10, 100 and 1000-agent profiles before raising a
  supported-capacity claim.

These are acceptance objectives, not measured production capacity until a named report is
checked into or linked from release evidence.

## 24-48 hour soak

Run on a dedicated host that will not be reclaimed:

    PYTHONPATH=backend python tools/benchmarking/soak.py \
      --server https://mesh.example.com \
      --duration-hours 24 \
      --devices 1000 \
      --api-metrics-url http://127.0.0.1:18000/metrics \
      --worker-metrics-url http://127.0.0.1:19100/metrics \
      --redis-url redis://127.0.0.1:16379/0 \
      --websocket-url wss://mesh.example.com/ws/events \
      --output-dir artifacts/soak-24h

The soak is resumable through its credential cache/state file and records one load report plus
one PostgreSQL capacity report and one runtime snapshot per chunk. Runtime snapshots record API
and worker RSS, scheduler leadership, Redis memory/evictions/clients, and repeated authenticated
WebSocket connect-auth-heartbeat-close cycles. The direct metrics/Redis URLs should be exposed
only to the soak host or an isolated management network; the public Caddy endpoint intentionally
does not expose `/metrics`. A 48-hour run uses `--duration-hours 48`.

At completion the harness writes `capacity-summary.json`, comparing the first and last database
snapshots. It reports database bytes/hour, per-table row/byte/index growth, dead-tuple ratios,
maximum PostgreSQL connection utilization, minimum buffer-cache hit ratio and maximum p95/p99
latency/failure rate across all load chunks. Append-heavy tables crossing the configurable
10-million-row review threshold are listed as partition-review candidates; crossing the threshold
triggers engineering review rather than blindly enabling partitioning.

A soak is accepted only if all chunks stay within failure/p95 objectives and review of the
summary/snapshots shows no monotonic resource leak or uncontrolled storage/index growth.
The final summary fails review through warnings if worker leadership disappears, Redis evicts
keys, any WebSocket reconnect probe fails, or API/worker resident memory grows by both more than
100 MiB and 50% across the evidence window.

CI intentionally does not claim this evidence: a normal pull-request runner executes only short
acceptance tests. Roadmap item #46 remains incomplete until a real 24/48-hour report has been
executed and retained.
