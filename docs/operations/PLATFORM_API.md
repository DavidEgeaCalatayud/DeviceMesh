# Platform API and security

Agent Protocol v1 remains unchanged. `GET /api/v1/system/version` returns the distributable server version, supported protocol versions, required Alembic revision and minimum-version policies for Windows, Linux, macOS, distributed probes, Android, iOS and ESP32. `GET /api/v1/system/compatibility/{component}` evaluates a concrete client version/protocol pair. These endpoints require a human session in production.

| API | Authorization | Purpose |
|---|---|---|
| `POST /api/v1/auth/login` | username/password | issue access/refresh session |
| `POST /api/v1/auth/refresh` | refresh token | rotate tokens; invalidate the old session |
| `GET /api/v1/auth/me` | Viewer+ | current identity |
| `POST /api/v1/auth/logout` | Viewer+ | revoke current session |
| `/api/v1/admin/users` | Administrator | create/list accounts |
| `PATCH /api/v1/admin/users/{id}` | Administrator | enable/disable; disabled accounts lose sessions |
| `GET /api/v1/admin/audit-log` | Administrator | bounded audit history |
| `GET /api/v1/service-catalog` | Viewer+ | logical services, distinct from discovered TCP `/services` |
| `POST /api/v1/service-catalog` | Operator+ | create service |
| `PUT /api/v1/service-catalog/{id}/monitors/{monitorId}` | Operator+ | associate existing monitor |
| `GET /api/v1/incidents` and `/{id}` | Viewer+ | filtered list and timeline detail |
| `GET /api/v1/incidents/{id}/rca` | Viewer+ | explainable dependency/temporal/event/Syslog RCA candidates |
| `PATCH /api/v1/incidents/{id}` | Operator+ | status, severity, assignee, notes, root cause, resolution |
| `GET /api/v1/system/ecosystem` | Viewer+ | software readiness, runtime counts and external acceptance gates |
| `GET/POST /api/v1/service-catalog/{id}/slos` | Viewer+ / Operator+ | reports / create objective |
| Agent enrollment-token and credential administration | Administrator | machine lifecycle |
| `/api/v1/agents/*` | agent's existing credential scheme | agent ingestion/operations |
| `/api/v1/probes/*` | registered probe bearer token | synthetic work/results |
| `/api/v1/discovery/observations` | Operator+ or `Probe <registered-token>` | bounded discovery upload |
| `/metrics` | Operator+ | internal Prometheus scrape; Caddy does not expose it |

Development retains explicit `public_reads=true` compatibility. Production refuses this mode. Browser tokens are held in `sessionStorage`, never build-time `VITE_*` configuration or URLs. WebSockets authenticate in the first frame, with a five-second deadline, Origin validation, and expiry/revocation rechecks on client heartbeats. Idle clients are disconnected after 60 seconds.

Incidents keep the existing monitor detection identity for compatibility. Services associate monitors; the new catalogue does not yet consolidate simultaneous failures into one service incident. Workflow supports open → acknowledged/investigating → mitigated/resolved and explicit reopen; automatic recovery resolves the human phase and appends a timeline event. Manual resolution requires a note. Reopening is rejected if a newer open incident already exists for that monitor. Notes and updates persist alongside an audit record.

SLIs support both successful-check ratio and time-weighted availability. Error budgets are expressed in checks or seconds according to the configured SLI. Multi-window burn rates (1h/6h/24h) produce normal/warning/critical states, while stale/disabled monitoring remains unknown rather than healthy. Notification routing can consume incident/alert transitions through the durable outbox.

401 means missing/expired/revoked identity; 403 means insufficient role; 404 unknown entity; 409 invalid workflow transition/duplicate username; 422 invalid input; 429 login throttled. Responses include a server-generated `X-Request-ID`. GET list limits are bounded; service search and incident/admin pagination are supported. OpenAPI at `/docs` describes request schemas; it is not an authentication bypass.

Global mutation auditing covers authenticated human changes in addition to semantic domain audit events. Local accounts support MFA possession factors, session revocation and administrative recovery. Durable notification channels/routing are implemented. OIDC/LDAP and forgotten-password identity federation remain optional future integrations rather than V1 requirements.
