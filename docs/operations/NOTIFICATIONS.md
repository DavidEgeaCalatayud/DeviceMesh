# Alert notifications and routing

DeviceMesh routes alert lifecycle transitions through a durable PostgreSQL outbox. Alert evaluation and telemetry ingestion never call an external notification destination directly.

## Channel kinds

Operator-managed channels support:

- `webhook`: POST the canonical alert transition payload as JSON.
- `slack`: POST a compact text message to a Slack incoming-webhook URL.
- `email`: send the canonical payload through SMTP.

Channel records persist only a `secretRef`; endpoint credentials are not stored in PostgreSQL.

## Secret resolution

The scheduler worker resolves `secretRef` at delivery time in this order:

1. A UTF-8 file named exactly as the reference under `DEVICEMESH_NOTIFICATION_SECRET_DIRECTORY` (default `/run/secrets/devicemesh-notifications`).
2. An environment variable named `DEVICEMESH_NOTIFICATION_SECRET_<REFERENCE>`, uppercased with non-alphanumeric characters replaced by `_`.

For webhook and Slack channels, the secret value is the complete destination URL. Production requires HTTPS.

For email, the secret value is a JSON object such as:

```json
{
  "host": "smtp.example.net",
  "port": 587,
  "security": "starttls",
  "fromAddress": "devicemesh@example.net",
  "username": "devicemesh",
  "password": "replace-through-secret-management"
}
```

Recipients are non-secret channel configuration (`config.to`). In production, SMTP must use `starttls` or `ssl`.

## Routes

A route selects one channel and can filter on:

- transition: `opened`, `recovered`, or `both`;
- exact metric name;
- exact device ID.

Omitting metric/device filters makes the route apply to all values in that dimension. Disabled routes or channels do not enqueue new deliveries.

Alert transitions associated with an active maintenance window are intentionally suppressed from external notification routing. The alert and DeviceMesh event still exist for audit/history.

## Durable delivery

Matched transitions create a `notification_deliveries` outbox row. The dedupe key contains alert, transition, route and channel identifiers, so replaying the same transition cannot enqueue a duplicate delivery for the same route.

Only the elected scheduler worker delivers the outbox. Due rows are claimed with a database lease and `FOR UPDATE SKIP LOCKED`; a worker crash leaves them available again after the lease expires.

Failures use exponential backoff starting at five seconds and capped at one hour. After `DEVICEMESH_NOTIFICATION_DELIVERY_MAX_ATTEMPTS` attempts (default 8), the row becomes `dead`. Operators can inspect delivery state and explicitly retry dead/queued deliveries through the operator API. Delivered rows are immutable from that retry endpoint.

The stored `lastError` is intentionally limited to the exception type so destination credentials or remote response bodies cannot leak into the database or operator API.

## Operator API

The authenticated operator surface provides:

- `GET/POST /api/v1/operator/notification-channels`
- `PATCH /api/v1/operator/notification-channels/{id}/state`
- `GET/POST /api/v1/operator/notification-routes`
- `PATCH /api/v1/operator/notification-routes/{id}/state`
- `GET /api/v1/operator/notification-deliveries`
- `POST /api/v1/operator/notification-deliveries/{id}/retry`

Human mutation audit middleware records channel/route creation, state changes and retry requests like other authenticated operator mutations.
