# Distributed probe credentials

Distributed synthetic probes authenticate with a random bearer credential. DeviceMesh stores only the SHA-256 digest of that credential in PostgreSQL; the plaintext token is returned only when a probe is registered or its credential is rotated.

## Registration and lifetime

An administrator creates a probe with `POST /api/v1/operator/synthetic-probes`. The response contains the one-time plaintext token. Store it in a secret manager or a root-readable file on the probe host.

Probe credentials have a server-enforced **90-day lifetime**. Registration creates the initial lifecycle record and every token rotation starts a new 90-day validity period. Requests to `/api/v1/probes/*` made with an expired known credential receive HTTP `401` and must be recovered by rotating the token from an administrator session.

The lifecycle is maintained transactionally in PostgreSQL from the probe credential record, so registrations and token-hash rotations cannot omit expiry metadata.

## Runtime secret loading

The probe supports exactly one credential source:

- `DEVICEMESH_PROBE_TOKEN` for simple development deployments; or
- `DEVICEMESH_PROBE_TOKEN_FILE` for production/container/systemd secret mounts.

If both are configured, the probe refuses to start. An empty token file is also rejected.

## Rotation

Administrators rotate a credential with:

`POST /api/v1/operator/synthetic-probes/{probeId}/rotate-token`

Rotation replaces the stored token digest transactionally. The previous token stops authenticating immediately; there is no overlap window. The response contains the new plaintext token once and PostgreSQL renews the lifecycle expiry at the same time. Replace the probe's secret file and restart/reload the probe process.

## Runtime telemetry

Synthetic probe mode reports bounded operational telemetry to:

`POST /api/v1/probes/runtime-heartbeat`

The heartbeat contains only operational metadata, never credentials or synthetic-result bodies:

- installed probe package version;
- process uptime;
- durable result queue depth and capacity;
- configured maximum concurrent checks.

The heartbeat also refreshes the probe's ordinary `lastSeenAt`. Operators can inspect the latest runtime state and credential lifecycle through:

`GET /api/v1/operator/synthetic-probes/{probeId}/runtime`

This makes it possible to distinguish a healthy probe from one that is online but accumulating queued results or approaching credential expiry.

Runtime telemetry failures are non-fatal to the synthetic loop. The probe logs the inability to report runtime status and continues its normal backoff/retry behaviour for work and queued results.

## Revocation

Disabling a probe with its existing administrator state endpoint immediately prevents token authentication and work claims. Re-enabling the probe does not change its token; use rotation whenever credential compromise is suspected.

## Operational guidance

- Prefer file-backed credentials outside development.
- Set file permissions so only the probe service account can read the token.
- Rotate credentials before the 90-day expiry boundary and immediately after suspected exposure.
- Alert operationally on a high `queueDepth / queueCapacity` ratio or stale `reportedAt` value.
- Never place the token in URLs, logs, images or repository files.
- Token rotation is captured by the global mutation audit middleware because it is an authenticated mutating operator endpoint.
