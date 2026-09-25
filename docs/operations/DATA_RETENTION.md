# Data retention

DeviceMesh applies bounded retention from the elected background worker. The policy is intentionally conservative: detailed data is compacted before it is deleted, while records needed for incident and audit history are not removed by this job.

## Default policy

| Dataset | Default | Behaviour |
| --- | ---: | --- |
| Raw telemetry | 7 days | Aggregated into hourly min/avg/max/sample-count rollups, then deleted. |
| Hourly telemetry rollups | 365 days | Deleted after the configured hourly retention window. |
| Device events | 90 days | Deleted after the configured event retention window. |
| Synthetic check results | 90 days | Deleted after the configured synthetic retention window. The minimum is 90 days so supported 90-day SLO windows retain their input data. |
| Service incidents | Unlimited by this policy | Preserved for incident history and postmortems. |
| Human audit log | Unlimited by this policy | Preserved as the security/operator audit ledger. |

The elected worker runs the policy every hour by default. PostgreSQL advisory-lock leadership ensures only one worker instance executes scheduled retention work at a time.

## Configuration

The policy is controlled through environment variables:

- `DEVICEMESH_RETENTION_RUN_INTERVAL_SECONDS`
- `DEVICEMESH_TELEMETRY_RAW_RETENTION_DAYS`
- `DEVICEMESH_TELEMETRY_HOURLY_RETENTION_DAYS`
- `DEVICEMESH_EVENT_RETENTION_DAYS`
- `DEVICEMESH_SYNTHETIC_CHECK_RETENTION_DAYS`

Hourly telemetry retention must be longer than raw telemetry retention. Synthetic check retention cannot be configured below 90 days.

Operators can inspect the effective runtime configuration with `GET /api/v1/operator/telemetry/retention-policy`. Manual raw telemetry compaction remains available through `POST /api/v1/operator/telemetry/compact` for maintenance and validation.

## Observability

The worker exports:

- `devicemesh_worker_runs_total{job="retention",outcome=...}`
- `devicemesh_worker_last_success_timestamp_seconds{job="retention"}`
- `devicemesh_retention_rollups_touched_total`
- `devicemesh_retention_deleted_rows_total{dataset=...}`

A retention failure is recorded as a failed worker iteration and retried on the next scheduler pass; the leader process continues serving the other scheduled jobs.
