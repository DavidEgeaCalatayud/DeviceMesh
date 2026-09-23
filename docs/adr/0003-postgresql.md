# ADR-0003: PostgreSQL persistence

**Status:** Accepted

## Decision
Use PostgreSQL for durable platform data and telemetry in V1. Introduce TimescaleDB only when measured retention/query requirements justify it.

## Consequences
V1 stays operationally simple while preserving an upgrade path for time-series workloads.
