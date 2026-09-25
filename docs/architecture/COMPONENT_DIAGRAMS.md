# C4 Level 3 — Component Diagrams

These diagrams document the internal component boundaries that matter operationally. They intentionally describe stable responsibilities and dependencies rather than individual classes.

## Backend API

```mermaid
flowchart LR
    http["HTTP / WebSocket adapters\nFastAPI routers + middleware"]
    auth["Security boundary\nHuman auth, RBAC, agent/probe auth, replay protection"]
    app["Application use cases\nIngestion, discovery, operations, lifecycle workflows"]
    domain["Domain model\nDevices, telemetry, alerts, events"]
    platform["Platform services\nCatalog, incidents, SLOs, synthetics"]
    repos["Repository adapters\nSQLAlchemy"]
    realtime["Realtime publisher\nRedis/in-process adapter"]
    db[("PostgreSQL")]
    redis[("Redis")]

    http --> auth
    auth --> app
    http --> platform
    app --> domain
    app --> repos
    platform --> repos
    app --> realtime
    platform --> realtime
    repos --> db
    realtime --> redis
```

### Backend component responsibilities

| Component | Responsibility |
|---|---|
| API routers | HTTP validation/serialization, dependency injection and protocol-specific status handling. |
| Request/mutation middleware | Request IDs, metrics, safe structured access logs and global audit coverage for authenticated mutations. |
| Human security | Argon2id credentials, roles, access/refresh sessions, revocation and user administration. |
| Machine security | Enrollment, per-agent/probe credentials, timestamp/nonce validation and replay prevention. |
| Application use cases | Coordinate domain behaviour without owning persistence technology. |
| Domain | Device/telemetry/event/alert concepts and rules independent of FastAPI/SQLAlchemy. |
| Platform repositories/services | Services/groups/dependencies, incident workflow/correlation, SLO/error budgets and synthetic state. |
| SQL repositories | Persist durable state and implement concurrency/transaction boundaries. |
| Realtime publisher | Decouple persisted events from WebSocket delivery and support multiple API replicas through Redis. |

## Scheduler worker

```mermaid
flowchart LR
    loop["Scheduler loop"] --> election["PostgreSQL advisory-lock leadership"]
    election --> offline["Offline device sweeper"]
    election --> synth["Synthetic scheduler"]
    election --> retention["Retention policy"]
    offline --> db[("PostgreSQL")]
    synth --> db
    retention --> db
    offline --> events["Realtime event publisher"]
    synth --> events
    events --> redis[("Redis")]
    metrics["Prometheus metrics listener :9100"] --- loop
```

The worker contains no durable scheduler lease in memory. Leadership belongs to the PostgreSQL session, so process/session loss releases the lock and allows a standby to take over.

## Web application

```mermaid
flowchart LR
    app["App shell + hash routing"]
    session["Session/API adapter\naccess + refresh handling"]
    search["Global search"]
    dashboard["Overview/dashboard"]
    services["Services + SLOs"]
    incidents["Incident management"]
    admin["Administration + audit"]
    ops["Operations / probes console"]
    ws["WebSocket event client"]

    app --> search
    app --> dashboard
    app --> services
    app --> incidents
    app --> admin
    app --> ops
    dashboard --> session
    services --> session
    incidents --> session
    admin --> session
    ops --> session
    search --> session
    dashboard --> ws
```

The web application stores human access/refresh tokens in browser session storage, retries one failed request through refresh, and returns to the login route when refresh cannot restore the session.

## Host agents

```mermaid
flowchart LR
    lifecycle["Service lifecycle / configuration"]
    identity["Host identity provider"]
    collectors["Telemetry collectors"]
    ops["Remote operation executor"]
    credential["Platform credential store"]
    protocol["Protocol models / serializer"]
    client["Authenticated HTTP client"]

    lifecycle --> identity
    lifecycle --> collectors
    lifecycle --> ops
    lifecycle --> credential
    identity --> protocol
    collectors --> protocol
    ops --> protocol
    credential --> client
    protocol --> client
```

Windows, Linux and macOS use platform-native implementations but share the same protocol-v1 responsibilities: stable identity, heartbeat, telemetry and only explicitly supported declarative operations. Compatibility policy is published by the backend under `/api/v1/system/version`.

## Distributed probe

```mermaid
flowchart LR
    config["Configuration + credential loading"]
    discovery["Bounded discovery engine"]
    synthetics["Synthetic executor"]
    health["Probe health"]
    outbox[("Bounded SQLite outbox")]
    client["Authenticated server client"]

    config --> discovery
    config --> synthetics
    discovery --> outbox
    synthetics --> outbox
    health --> client
    outbox --> client
```

The probe deliberately separates network execution from server delivery. Temporary server/network failure therefore queues bounded local results rather than allowing unbounded memory/disk growth.

## Dependency direction

The backend follows the architectural rule `adapters → application/domain ← infrastructure adapters`. Domain/application code must not import FastAPI-specific presentation concerns. Runtime infrastructure (PostgreSQL, Redis, Prometheus/Grafana) remains replaceable at explicit adapter boundaries rather than leaking into domain objects.
