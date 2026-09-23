# DeviceMesh

**Local-first device observability and management, engineered as a multi-platform system rather than a single application.**

DeviceMesh discovers devices on networks you control, models stable device identity, ingests optional agent telemetry and builds a realtime inventory, event timeline, alerting surface and observed network view.

> **Current status:** active V1 implementation. PostgreSQL persistence, stable device identity, bounded LAN discovery, secure Windows-agent enrollment, host telemetry, offline/recovery lifecycle, realtime events, threshold alerts, bounded service inventory, observed network topology, Docker deployment and the React operator dashboard are implemented. Mobile clients, ESP32 capabilities, richer topology evidence and release-hardening work remain roadmap items.

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
 Windows Agent       Network Probe ESP32
   .NET/C#              Python      C
```

## Engineering principles

- Framework-independent domain/application layers.
- Stable device identity is not equivalent to an IP address.
- Versioned, language-neutral agent contracts with golden fixtures.
- Current state and append-only events are separate models.
- Local-first deployment; no mandatory cloud dependency.
- Separate human and agent trust domains.
- Network discovery is bounded to operator-authorized scopes.
- Service inventory uses an explicit port allowlist and connect-only checks.
- Approximate topology is labelled as inference rather than physical truth.
- CI, security scanning, SBOM and observability are product concerns.

## Repository

| Area | Technology | Purpose |
|---|---|---|
| `backend/` | Python, FastAPI | API, ingestion, domain/application layers |
| `web/` | React, TypeScript | operator dashboard |
| `agents/windows/` | C#/.NET | V1 reference host agent |
| `agents/linux/`, `agents/probe/` | Python | later Linux agent and bounded discovery probe |
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

## Network probe

The probe requires an explicit CIDR allowlist. Optional TCP service inventory is disabled unless `DEVICEMESH_PROBE_TCP_PORTS` is configured.

```bash
export DEVICEMESH_PROBE_SCOPES="192.168.1.0/24"
export DEVICEMESH_PROBE_TCP_PORTS="22,80,443,445,3389"
python -m devicemesh_probe --scope 192.168.1.0/24
```

See [Network Probe operations](docs/operations/NETWORK_PROBE.md) for the safety model, bounds and service lifecycle semantics.

## Protocol v1

The machine-readable contracts in `protocol/schemas/` define heartbeat, telemetry, events and an intentionally restricted command allowlist. Fixtures under `protocol/fixtures/` are intended to be consumed by every maintained language implementation.

## V1 target

V1 closes only when the complete acceptance path is proven from a clean deployment: migrations, operator/agent trust, discovery, Windows telemetry, realtime state, alert lifecycle, durable recovery, backup/restore, operational health and reproducible release artifacts.

See [ROADMAP.md](ROADMAP.md), [architecture](docs/architecture/ARCHITECTURE.md), [requirements](docs/product/REQUIREMENTS.md), [threat model](docs/security/THREAT_MODEL.md) and [ADRs](docs/adr/).
