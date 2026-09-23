# ADR-0004: WebSockets for realtime clients

**Status:** Accepted

Device state, events and alerts benefit from server push. WebSockets are used for client realtime updates while ingestion remains ordinary authenticated HTTP in V1. This keeps agent retry/idempotency semantics simpler.
