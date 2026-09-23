# Operational health, maintenance and controlled remote operations

DeviceMesh V1.1 extends device observability with persisted availability history and a deliberately narrow remote-operation channel.

## Availability model

Availability is stored as state intervals rather than reconstructed from the current `devices.status` value.

An interval records:

- device
- `online` or `offline`
- start time
- optional end time
- transition source

The heartbeat timeout sweeper timestamps an outage at `last_seen + offline_after`, not at the later sweep execution time. This avoids crediting a device with availability during a period in which it had already stopped reporting.

Repeated observations in the same state do not create extra intervals. A real state transition closes the previous interval and opens the next one.

### SLA windows

`GET /api/v1/devices/{deviceId}/health` returns 24-hour, 7-day and 30-day summaries.

Each window reports:

- monitored seconds
- online seconds
- downtime seconds
- availability percentage
- outage count
- longest outage
- mean duration of recovered outages (an MTTR-like indicator)

Availability is calculated over **monitored time only**:

```text
availability = online_seconds / (online_seconds + downtime_seconds) * 100
```

Time before DeviceMesh has an availability interval for a device is not silently classified as downtime or uptime. A new installation can therefore show less than 24 hours of monitored coverage in the `24h` window.

Open outages are clipped to the query time, so their duration continues to grow until an online transition is recorded.

`GET /api/v1/devices/{deviceId}/outages?days=30` exposes the underlying outage history used by the UI.

## Maintenance windows and alert silencing

Maintenance can be device-specific or global (`deviceId = null`).

Create a window with the operator token:

```http
POST /api/v1/operator/maintenance-windows
Authorization: Bearer <operator-token>
Content-Type: application/json

{
  "deviceId": "agent-workstation-01",
  "startsAt": "2026-09-23T18:00:00Z",
  "endsAt": "2026-09-23T19:00:00Z",
  "reason": "Planned OS patching"
}
```

Cancel it with:

```http
POST /api/v1/operator/maintenance-windows/{windowId}/cancel
Authorization: Bearer <operator-token>
```

A maintenance window does **not** stop ingestion, delete an incident or rewrite telemetry. Threshold evaluation continues normally.

If an incident opens during maintenance, it records the maintenance window that silenced it. An already-open incident is also presented as silenced while an applicable maintenance window is currently active.

This preserves the factual incident history while allowing notification/action layers and the UI to distinguish expected maintenance noise from an unscheduled incident.

Maintenance create/cancel operations are written to the security audit stream. Device-scoped maintenance also appears in the device event timeline.

## Controlled remote operations

Remote operations are pull-based. The server never opens an inbound connection to an agent.

```text
operator -> queue -> PostgreSQL -> authenticated agent claims -> agent executes allowlist -> completion
```

V1.1 allows exactly:

- `telemetry.collect`
- `inventory.refresh`
- `agent.health_check`

These operations accept **no arguments** in V1.1.

There is intentionally no generic command primitive such as:

- `shell.execute`
- `powershell.execute`
- `bash.execute`
- arbitrary executable path
- command text passed as an argument

Adding a new operation requires a new explicit operation type and a corresponding implementation in each supported agent.

### Queue an operation

```http
POST /api/v1/operator/remote-operations
Authorization: Bearer <operator-token>
Content-Type: application/json

{
  "deviceId": "agent-workstation-01",
  "operationType": "agent.health_check",
  "arguments": {},
  "ttlSeconds": 300
}
```

The server binds the operation to the enrolled agent associated with the target device.

### Lifecycle

```text
queued -> claimed -> succeeded
                  -> failed
       -> expired
claimed ----------> expired
```

The target agent must authenticate using its existing DeviceMesh agent credential to claim or complete an operation. Another agent cannot complete it.

Claim uses a database row lock with `SKIP LOCKED`, preventing concurrent pollers from receiving the same operation. A queued or claimed operation that passes `expiresAt` becomes `expired`; late completion is rejected.

Queue, claim, completion and expiry transitions are written to the security audit stream.

### Agent endpoints

Authenticated agents use:

```text
POST /api/v1/agents/operations/claim
POST /api/v1/agents/operations/{operationId}/complete
```

No pending operation returns HTTP `204` from the claim endpoint.

## Operational guidance

- Use short TTLs for interactive requests. The API accepts 30–3600 seconds.
- Prefer maintenance windows over disabling alert rules for planned work; rule history remains intact.
- Treat availability as DeviceMesh-observed availability, not a substitute for an external user-facing SLA probe.
- Review security audit events when investigating remote-operation or maintenance activity.
- Keep agent credentials separate from operator credentials.
