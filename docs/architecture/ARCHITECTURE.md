# DeviceMesh Architecture

DeviceMesh is a local-first distributed observability and operations platform. The architecture documentation follows the C4 model so system boundaries, runtime containers and important internal components can be read at progressively deeper levels.

## C4 model

1. **[System Context](SYSTEM_CONTEXT.md)** — people, managed systems, monitored targets and the DeviceMesh trust boundary.
2. **[Container Diagram](CONTAINER_DIAGRAM.md)** — web, API, worker, PostgreSQL, Redis, Prometheus/Grafana, host agents and distributed probes.
3. **[Component Diagrams](COMPONENT_DIAGRAMS.md)** — backend API, scheduler worker, web application, host agents and distributed-probe internals.
4. **[Deployment View](DEPLOYMENT.md)** — production Compose topology, exposure, persistence, scaling and failure-domain boundaries.

Supporting views:

- **[Data Flow](DATA_FLOW.md)** — ingestion and event-flow narrative.
- **[Synthetic Consensus](SYNTHETIC_CONSENSUS.md)** — distributed synthetic decision semantics.
- **ADRs** under `docs/adr/` — architectural decisions and trade-offs.

## Architectural boundaries

- **Domain**: device identity, telemetry, events, alerts and protocol-independent rules.
- **Application**: use cases and orchestration.
- **Infrastructure**: PostgreSQL, Redis, discovery, platform collectors, transport and external adapters.
- **API**: FastAPI HTTP/WebSocket adapters plus auth, metrics, logging and audit middleware.
- **Workers**: independently deployable scheduled jobs with PostgreSQL-backed leader election.
- **Agents/probes**: platform-specific collectors/executors using a versioned machine protocol.
- **Clients**: browser and future production mobile presentation layers.

## Dependency rules

Backend domain/application code must not depend on FastAPI presentation concerns. Durable state is accessed through repository adapters; realtime fan-out is behind an event-publisher adapter. Protocol schemas live outside any implementation so Python, C#, Swift and future Kotlin/C clients can validate against the same wire contract.

PostgreSQL is the durable system of record. Redis is intentionally non-authoritative and provides cross-process realtime coordination. API replicas therefore remain replaceable/stateless at the application tier, while scheduled work is owned by a PostgreSQL advisory-lock leader rather than by one fixed process.

## Scope markers

The C4 diagrams distinguish production-capable components from scaffolds. Windows, Linux, macOS and the distributed host probe participate in the current protocol-v1 compatibility matrix. Android, iOS and ESP32 remain roadmap clients until their production contracts and release/testing requirements are implemented.
