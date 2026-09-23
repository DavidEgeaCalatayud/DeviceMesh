# DeviceMesh

**Local-first device observability and management, engineered as a multi-platform system rather than a single application.**

DeviceMesh discovers devices on networks you control, models stable device identity, ingests optional agent telemetry and builds a realtime inventory, event timeline and alerting surface.

> **Current status:** engineering foundation. Core protocol, backend bootstrap, web dashboard, Windows agent, Android/iOS scaffolds, ESP32 firmware structure, Docker and CI are implemented. Production authentication, persistent repositories, full discovery and V1 product flows remain roadmap work.

## Architecture at a glance

```text
                  Web · Android · iOS
                         |
                    HTTPS / WSS
                         |
                   DeviceMesh API
                  Python / FastAPI
                         |
               +---------+---------+
               |                   |
          PostgreSQL             Redis
               ^
               |
          Agent Protocol v1
               |
      +--------+---------+---------+
      |                  |         |
 Windows Agent       Linux/Probe  ESP32
   .NET/C#              Python      C
```

## Engineering principles

- Framework-independent domain/application layers.
- Stable device identity is not equivalent to an IP address.
- Versioned, language-neutral agent contracts with golden fixtures.
- Current state and append-only events are separate models.
- Local-first deployment; no mandatory cloud dependency.
- Separate human and agent trust domains.
- CI, security scanning, SBOM and observability are product concerns.

## Repository

| Area | Technology | Purpose |
|---|---|---|
| `backend/` | Python, FastAPI | API, ingestion, domain/application layers |
| `web/` | React, TypeScript | operator dashboard |
| `agents/windows/` | C#/.NET | V1 reference host agent |
| `agents/linux/`, `agents/probe/` | Python | later Linux agent and discovery probe |
| `mobile/android/` | Kotlin, Compose | modular Android client |
| `mobile/ios/` | Swift, SwiftUI | iOS client scaffold |
| `firmware/esp32/` | C, ESP-IDF | edge probe scaffold |
| `protocol/` | JSON Schema | cross-language wire contracts |
| `infra/` | Docker, PostgreSQL, Redis | local deployment |
| `docs/adr/` | ADRs | architectural decisions and trade-offs |

## Quick start

```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up --build
```

Then open `http://localhost:5173` and check `http://localhost:8000/health`.

For backend development:

```bash
cd backend
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Protocol v1

The machine-readable contracts in `protocol/schemas/` define heartbeat, telemetry, events and an intentionally restricted command allowlist. Fixtures under `protocol/fixtures/` are intended to be consumed by every maintained language implementation.

## V1 target

V1 closes only when the platform has PostgreSQL-backed device state, scoped LAN discovery, authenticated Windows-agent enrollment, CPU/RAM/disk/network telemetry, realtime events, threshold alerts, the web dashboard, Docker deployment and unit/integration/contract/E2E coverage.

See [ROADMAP.md](ROADMAP.md), [architecture](docs/architecture/ARCHITECTURE.md), [requirements](docs/product/REQUIREMENTS.md), [threat model](docs/security/THREAT_MODEL.md) and [ADRs](docs/adr/).
