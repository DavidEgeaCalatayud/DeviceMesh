# Failure and recovery matrix

DeviceMesh failure testing combines focused security/concurrency tests with a production-format Docker acceptance workflow. A scenario is not considered covered merely because retry code exists; the expected degraded behaviour and recovery are asserted.

## Automated matrix

| Failure | Expected behaviour | Recovery assertion | Coverage |
|---|---|---|---|
| PostgreSQL unavailable | `/ready` returns `503`; process stays available for liveness/diagnostics rather than claiming readiness. | PostgreSQL restart returns `/ready` to `200`, worker reacquires scheduler leadership and pre-failure durable state is present. | `failure-acceptance.yml` |
| Redis unavailable | Durable API/database operations remain ready; realtime publication may be temporarily unavailable and is logged/retried. | Redis restart reaches `PONG`; the normal enrollment→heartbeat→Redis/WebSocket→inventory acceptance harness passes again. | `failure-acceptance.yml` |
| API process stopped | Public API endpoint is unreachable while the container is stopped. | API restart returns `/ready` to `200` and the pre-failure service-catalog canary remains present. | `failure-acceptance.yml` |
| Worker process stopped | Worker metrics listener disappears and scheduled work is unavailable for the outage interval. | Worker restart exposes metrics and reports `devicemesh_worker_leader 1`. | `failure-acceptance.yml` |
| Scheduler leader DB session lost | Standby cannot hold the same advisory lock concurrently. | Invalidating the leader session releases PostgreSQL's session-scoped lock and a standby session acquires it. | `backend/tests/integration/test_worker_leader_failover.py` |
| Human refresh token reused/revoked | Replayed/revoked refresh material is rejected. | A valid current session can continue according to the rotation policy. | human-auth/security tests |
| Agent timestamp/nonce replay | Stale timestamps or repeated nonces are rejected. | A fresh authenticated request with a new nonce succeeds. | agent-auth contract/integration tests |
| Probe/result replay | Previously accepted/replayed result identity is not processed twice. | Fresh valid work/result flow continues. | distributed synthetic/security tests |
| Probe offline outbox delivery interruption | Results remain in a bounded persistent local queue rather than unbounded memory. | Retry drains queued work after connectivity returns while respecting queue bounds. | probe outbox tests |

## Production failure workflow

`.github/workflows/failure-acceptance.yml` starts the same hardened Compose definition used by production acceptance, exposing only temporary loopback test ports for the API and worker metrics listener. It then executes `tools/deployment/failure-acceptance.sh`.

The harness creates a durable `failure-canary` before disruption. That canary is checked after database and API recovery so a green result proves more than process restart: persisted product state survived the injected failures.

Redis is deliberately non-authoritative. During its outage the API remains database-ready; after Redis returns, the existing realtime acceptance harness proves WebSocket fan-out recovers end-to-end rather than checking only `redis-cli ping`.

## Failure-domain boundary

This matrix validates DeviceMesh application behaviour on one CI host. It does not simulate independent physical hosts, DNS provider outages, certificate-authority outages, storage corruption, kernel/network partitions between arbitrary hosts, or PostgreSQL/Redis cluster failover supplied by an external infrastructure platform. Those belong to deployment/infrastructure HA acceptance rather than the application failure contract.

## Adding a failure mode

Every new production runtime dependency or durable coordination mechanism must add one of:

1. a deterministic automated failure/recovery scenario in `failure-acceptance.yml`; or
2. a focused integration test when the dependency can be faithfully modelled at the protocol/session boundary.

The documented matrix must identify both the degraded-state expectation and the recovery assertion.
