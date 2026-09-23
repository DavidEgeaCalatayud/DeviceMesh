# Message Formats

- `heartbeat`: liveness only.
- `telemetry`: bounded metric batch.
- `event`: meaningful agent-observed state transition.
- `command`: server request from an allowlist; V1 intentionally excludes arbitrary command execution.

Timestamps use RFC 3339/ISO-8601 UTC values.
