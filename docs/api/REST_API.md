# DeviceMesh REST API

DeviceMesh exposes a versioned JSON API under `/api/v1`, plus health/readiness and internal observability endpoints. FastAPI publishes the exact machine-readable contract at `/openapi.json` and the interactive reference at `/docs`.

The exhaustive, reviewable route list is generated from that same OpenAPI document into [ENDPOINT_CATALOG.md](ENDPOINT_CATALOG.md). CI regenerates the catalog whenever API or documentation code changes, so the committed reference cannot silently drift from the application.

## Entry points

| Entry point | Purpose |
|---|---|
| `GET /health` | Process liveness. Does not certify database readiness. |
| `GET /ready` | Readiness including database availability and required Alembic revision. |
| `GET /openapi.json` | Authoritative OpenAPI schema. |
| `GET /docs` | FastAPI Swagger UI. |
| `/api/v1/*` | Versioned DeviceMesh product API. |
| `GET /metrics` | Protected Prometheus metrics endpoint; intentionally hidden from OpenAPI. |
| `WebSocket /ws/events` | Realtime device/platform event stream. |

## Authentication model

DeviceMesh deliberately separates **human sessions** from **machine credentials**.

### Human authentication

`POST /api/v1/auth/login` accepts username/password and returns an access token plus rotating refresh token. `POST /api/v1/auth/refresh` rotates the refresh session. `POST /api/v1/auth/logout` revokes the active session, while `/api/v1/auth/me` returns the current human principal.

Production defaults to private reads. The application-level access gate therefore requires a valid human session for ordinary operator reads unless `DEVICEMESH_PUBLIC_READS=true` is explicitly enabled. Mutating endpoints apply role checks on top of that gate; administrative user/security operations require administrator privileges.

Human tokens must be sent as:

```text
Authorization: Bearer <access-token>
```

The browser WebSocket does not put credentials in the URL. In private-read mode it connects and sends the bearer token in the first client frame; subsequent client heartbeats re-check expiry/revocation.

### Agent authentication

Agents are enrolled with a one-time enrollment token created by an operator. After enrollment, an agent uses its independent credential and anti-replay headers for heartbeat, telemetry and remote-operation polling/results.

Typical authenticated machine request headers are:

```text
Authorization: Agent <credential>
X-DeviceMesh-Agent-ID: <agent-id>
X-DeviceMesh-Timestamp: <RFC3339 timestamp>
X-DeviceMesh-Nonce: <unique nonce>
```

The timestamp window and nonce store prevent replay. Human bearer tokens are not valid agent credentials and agent credentials are not valid human sessions.

### Distributed probe authentication

Distributed probes receive a random bearer credential at registration/rotation. DeviceMesh stores only its digest. Probe credentials can be rotated independently and disabling a probe prevents it from authenticating/claiming work.

## API families

The generated endpoint catalog contains every current method/path. The families below explain the intent and security boundary of those endpoints.

### System and compatibility

System routes expose server/API/protocol/schema versions and the production client compatibility matrix. `GET /api/v1/system/compatibility/{component}` evaluates a concrete package version and protocol version before rollout.

### Authentication and user administration

Auth routes cover login, refresh, logout, current-principal inspection and administrator user lifecycle. Password material is hashed with Argon2id; refresh sessions rotate and can be revoked.

### Enrollment and agent ingestion

Enrollment routes mint one-time enrollment tokens and exchange them for agent credentials. Agent routes accept protocol-v1 heartbeat/telemetry and provide the machine side of declarative remote operations.

### Device inventory and events

Device routes expose persisted inventory/state. Event routes expose the durable event timeline used by the web UI and realtime stream.

### Telemetry and network diagnostics

Telemetry routes expose latest samples, bounded history/rollups and derived network diagnostics. Query parameters constrain device, metric, time window, resolution and result limits.

### Alerts, maintenance and operational health

Threshold rules/incidents, maintenance windows, outages and operational-health routes provide the device-level alerting and availability model. These are separate from Prometheus rules that monitor DeviceMesh itself.

### Discovery and network topology

Discovery routes ingest/report observed assets and services; network routes expose the current approximate topology and service inventory derived from observations.

### Synthetic monitoring and distributed probes

Synthetic routes manage monitor definitions/results/health and probe registration/work/result submission. Synthetic checks can execute server-side or through distributed probes depending on monitor placement/configuration.

### Service catalog, incidents and SLOs

Platform routes model services, service groups, hard/soft dependencies, monitor association, incident workflow/correlation/postmortems and SLO/error-budget reports. SLOs support check-ratio and time-weighted availability modes.

### Remote operations

Operator routes queue only supported declarative operations. Agents claim one operation and submit its result. This is not an arbitrary remote shell interface.

### Audit

Audit routes expose the immutable operator-facing audit history. Domain mutations record semantic audit events and the global mutation middleware covers successful authenticated human mutations that do not yet have their own semantic event.

## Request/response conventions

- JSON request bodies reject unknown fields where the Pydantic model uses `extra="forbid"`.
- Timestamps are UTC/RFC3339 values at API boundaries.
- Collection endpoints use explicit bounded limits; several use `offset` pagination.
- IDs are opaque strings unless the specific contract states otherwise.
- A successful DELETE may return `204 No Content`.
- Validation errors use FastAPI/Pydantic `422` responses.
- Authentication failures use `401`; insufficient role/permission uses `403`.
- Missing resources use `404`; state conflicts/transitions commonly use `409`.
- Throttled login/security paths may return `429`.
- `/ready` returns `503` when the database is unavailable or requires migration.

## Correlation and observability

HTTP responses include `X-Request-ID`. A safe incoming request ID may be propagated; otherwise DeviceMesh generates one. The same ID is bound into structured backend logs and mutation-audit metadata so an operator can correlate a client failure with server execution.

Request/response bodies, authorization headers and raw query strings are deliberately excluded from structured access logs.

## Compatibility and change policy

See [COMPATIBILITY.md](COMPATIBILITY.md). The `/api/v1` HTTP namespace and machine `protocolVersion` are related but independent compatibility boundaries. Breaking wire changes require a protocol-version change rather than relying on package version alone.

## Regenerating the endpoint reference

After adding/removing/changing routes:

```bash
python tools/docs/render_api_catalog.py
```

Commit the resulting `docs/api/ENDPOINT_CATALOG.md`. Documentation CI generates the reference from the running FastAPI OpenAPI model and verifies the committed file, preventing undocumented endpoints from entering `main`.
