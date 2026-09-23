# Architecture

DeviceMesh is a local-first distributed observability platform.

```text
Web / Android / iOS
        |
    HTTPS / WSS
        |
   DeviceMesh API
        |
  +-----+------+----------------+
  |            |                |
PostgreSQL   Redis         Event/Alert engine
        ^
        |
Agent Protocol v1
        |
Windows / Linux / ESP32
```

## Boundaries

- **Domain**: device identity, telemetry, events, alerts and agent semantics.
- **Application**: use cases and orchestration.
- **Infrastructure**: PostgreSQL, Redis, discovery, transport and third-party adapters.
- **API**: HTTP/WebSocket delivery.
- **Agents**: platform-specific collectors that publish protocol messages.
- **Clients**: presentation and user interaction.

The backend domain does not import FastAPI, SQLAlchemy or Redis. Protocol schemas live outside any implementation so Python, C#, Kotlin, Swift and C can validate against the same contract.
