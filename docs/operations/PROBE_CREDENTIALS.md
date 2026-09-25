# Distributed probe credentials

Distributed synthetic probes authenticate with a random bearer credential. DeviceMesh stores only the SHA-256 digest of that credential in PostgreSQL; the plaintext token is returned only when a probe is registered or its credential is rotated.

## Registration

An administrator creates a probe with `POST /api/v1/operator/synthetic-probes`. The response contains the one-time plaintext token. Store it in a secret manager or a root-readable file on the probe host.

## Runtime secret loading

The probe supports exactly one credential source:

- `DEVICEMESH_PROBE_TOKEN` for simple development deployments; or
- `DEVICEMESH_PROBE_TOKEN_FILE` for production/container/systemd secret mounts.

If both are configured, the probe refuses to start. An empty token file is also rejected.

## Rotation

Administrators rotate a credential with:

`POST /api/v1/operator/synthetic-probes/{probeId}/rotate-token`

Rotation replaces the stored token digest transactionally. The previous token stops authenticating immediately; there is no overlap window. The response contains the new plaintext token once. Replace the probe's secret file and restart/reload the probe process.

## Revocation

Disabling a probe with its existing administrator state endpoint immediately prevents token authentication and work claims. Re-enabling the probe does not change its token; use rotation whenever credential compromise is suspected.

## Operational guidance

- Prefer file-backed credentials outside development.
- Set file permissions so only the probe service account can read the token.
- Rotate after suspected exposure and during planned credential maintenance.
- Never place the token in URLs, logs, images or repository files.
- Token rotation is captured by the global mutation audit middleware because it is an authenticated mutating operator endpoint.
