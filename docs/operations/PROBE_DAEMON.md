# Distributed probe daemon candidate

Register a probe through the administrator-controlled operator console/API, store its returned token in a private environment file and configure `DEVICEMESH_SERVER_URL` with HTTPS. The existing LAN discovery scopes remain explicitly opt-in.

| Setting | Default | Meaning |
|---|---|---|
| `DEVICEMESH_PROBE_TOKEN` | none | registered probe credential |
| `DEVICEMESH_PROBE_CONCURRENCY` | 4 | at most 1–32 claimed/executing checks per batch |
| `DEVICEMESH_PROBE_QUEUE_PATH` | `data/probe-results.sqlite3` | persistent SQLite result outbox |
| `DEVICEMESH_PROBE_POLL_SECONDS` | 5 | normal work-poll interval |

Build `agents/probe/Dockerfile` or install the wheel into `/opt/devicemesh-probe` and review the systemd unit in `agents/probe/systemd/`. Mount `/data` persistently in Docker. The systemd unit uses a dynamic user, private temp, restricted filesystem and no capabilities; it cannot run privileged ICMP checks.

Results enter SQLite before delivery and retain their original `workId`/`checkedAt` across retries and process restarts. At most 10,000 pending results are retained; claiming pauses at capacity. Each batch bounds concurrency and serializes checks aimed at the same hostname. Total check deadlines include DNS. Delivery failures use exponential backoff plus jitter, capped at approximately five minutes.

HTTP 4xx responses are retained for operator investigation rather than silently discarded, so an invalid/deleted work item may block delivery until repaired. Queue expiry/dead-letter administration, queue encryption and probe health reporting are pending. Don't share one queue file between probe identities/processes. Filesystem failure can still prevent persistence and must be monitored.

The server validates check timestamps against work assignment/lease bounds with five-minute skew tolerance. Delayed results enrich history without rewinding the live incident state. Lease idempotency is serialized under a row lock. Results are observations by a trusted probe, not cryptographic evidence of network state; signed reports/mTLS and credential expiry remain pending.
