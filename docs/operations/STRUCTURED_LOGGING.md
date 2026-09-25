# Structured logging

DeviceMesh writes backend runtime logs as one JSON object per line. The API and the independent scheduler worker share the same formatter so log collectors can query both processes with the same schema.

## Common fields

Every record contains:

- `timestamp`: UTC ISO-8601 timestamp.
- `level`: Python log level.
- `service`: runtime process (`api`, `scheduler-worker`, or the configured component name).
- `component`: logger name.
- `process_id`: operating-system process ID.
- `request_id`: HTTP correlation ID when a request is active; otherwise an empty string.
- `message`: stable operator-facing event text.

Safe domain context can add `device_id`, `incident_id`, `monitor_id`, `probe_id`, `service_id`, `job`, `status`, and `route`. Callers should use these structured fields instead of interpolating identifiers into message text when practical.

## HTTP correlation

`RequestMetricsMiddleware` accepts an incoming `X-Request-ID` only when it is 1-64 ASCII characters from `A-Z`, `a-z`, `0-9`, `.`, `_`, or `-`. A missing or invalid value is replaced with a locally generated 32-character ID. The selected ID is:

1. stored in ASGI request state;
2. bound to the logging context;
3. returned as `X-Request-ID` in the HTTP response;
4. included in DeviceMesh request logs and logs emitted while handling that request.

This makes correlation work through a trusted reverse proxy while preventing arbitrary header content from becoming log data.

## Background jobs

The independent scheduler process identifies itself as `service=scheduler-worker`. Each scheduled iteration binds its job name (`offline`, `synthetics`, or `retention`) to the log context. Exceptions therefore remain attributable to the worker operation even when execution crosses `asyncio.to_thread`.

When workers are embedded for development, the process service remains `api`, while the `job` field still identifies background activity.

## Sensitive-data policy

The structured formatter intentionally does not serialize request/response bodies, HTTP headers, query strings, bearer tokens, database URLs, or exception messages. For exceptions it records only `exception_type`; traceback rendering is not added to the JSON payload.

Uvicorn access logging is disabled because raw access records can expose request-target details. DeviceMesh emits its own request-completion record from the metrics middleware using the resolved route template and status code instead.

Do not add secrets to `extra={...}` fields. Domain context is allow-listed by the formatter.

## Example

```json
{"timestamp":"2026-09-25T13:00:00+00:00","level":"INFO","service":"api","component":"devicemesh.http","process_id":1234,"request_id":"edge-01","message":"request completed","status":200,"route":"/api/v1/devices/{device_id}"}
```

For worker failures, search by `service=scheduler-worker` and `job=<name>`. For an API incident, begin with `request_id`, then pivot to the relevant domain identifier when present.
