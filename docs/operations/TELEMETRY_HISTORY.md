# Telemetry history and network diagnostics

DeviceMesh stores raw metric samples in PostgreSQL and exposes bounded history queries for charts and diagnostics. Raw measurements remain the source of truth; diagnostic labels are derived and explicitly approximate.

## History API

`GET /api/v1/telemetry/history`

Required query parameters:

- `deviceId`: stable DeviceMesh device id;
- `name`: metric name;
- `start` and `end`: timezone-aware timestamps.

Optional parameters:

- `bucketSeconds`: average samples into time buckets while also returning minimum, maximum and sample count;
- `limit`: maximum returned raw samples or buckets, capped at 5000.

A single query cannot span more than 30 days. The database index `ix_metric_samples_device_metric_timestamp` supports device/metric/time-window access without changing the append-only sample model.

## Network diagnostic API

`GET /api/v1/telemetry/network-diagnostics?deviceId=<id>&windowMinutes=15`

The V1 diagnostic uses window averages for latency, jitter and packet loss. It reports `healthy`, `degraded`, `poor` or `unknown`, plus signal coverage and human-readable reasons.

| Signal | Degraded | Poor |
|---|---:|---:|
| latency | >= 100 ms | >= 250 ms |
| jitter | >= 20 ms | >= 50 ms |
| packet loss | >= 1% | >= 5% |

The worst observed signal determines the state. Missing signals produce partial coverage; no signals produce `unknown`.

These thresholds are an operator-facing heuristic, not a root-cause engine. DeviceMesh does not infer Wi-Fi interference, ISP congestion, faulty cabling or another cause from these values alone.
