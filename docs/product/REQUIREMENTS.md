# Requirements

## Functional
- FR-001: discover devices within explicitly configured local scopes.
- FR-002: resolve observations into stable device identities.
- FR-003: enroll agents with expiring enrollment tokens.
- FR-004: ingest versioned heartbeat and telemetry payloads.
- FR-005: expose device inventory and history through authenticated APIs.
- FR-006: broadcast realtime state changes to connected clients.
- FR-007: evaluate threshold alert rules.

## Non-functional
- NFR-001: no core cloud dependency.
- NFR-002: protocol compatibility is contract-tested.
- NFR-003: secrets are externalized.
- NFR-004: services expose health/readiness signals.
- NFR-005: supported builds are reproducible in CI.
