# ADR-0002: FastAPI backend

**Status:** Accepted

## Context
The server needs typed HTTP/WebSocket APIs, async I/O and strong Python ecosystem support.

## Decision
Use FastAPI at the delivery boundary while keeping domain/application code framework-independent.

## Consequences
Pydantic schemas are API contracts, not domain entities. FastAPI imports do not enter the domain layer.
