# DeviceMesh

**Local-first device observability and management, engineered as a multi-platform system rather than a single application.**

DeviceMesh discovers devices on networks you control, models stable device identity, ingests optional agent telemetry and builds a realtime inventory, event timeline, alerting surface and observed network view.

> **Current status:** V1.3 plus a platform/deployment candidate. Windows/Linux/macOS agents, distributed probes, native Android/iOS operator clients, SNMPv3 NMS polling, LLDP/CDP physical topology and persistent Syslog are implemented in main. Human sessions/RBAC, service/incident/SLO workflows, Redis fan-out, workers, observability and production deployment/restore tooling are also present. Long soak/capacity evidence, full mobile E2E/distribution and production ESP32 hardware acceptance remain release gates.

See the [57-point implementation ledger](docs/product/IMPLEMENTATION_57_POINTS.md) for the exact scope and remaining work, [production deployment](docs/operations/PRODUCTION_DEPLOYMENT.md), [platform API/security](docs/operations/PLATFORM_API.md), [backup/restore](docs/operations/BACKUP_RESTORE.md) and [probe daemon](docs/operations/PROBE_DAEMON.md).

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
   +-------------+-------------+-------------+
   |             |             |             |
Windows Agent Linux Agent  macOS Agent  Network Probes
   .NET/C#       Python       Swift         Python
                                              |
                                           ESP32
                                              C
```

## Engineering principles

- Framework-independent domain/application layers.
- Stable device identity is not equivalent to an IP address.
- Versioned, language-neutral agent contracts with golden fixtures.
- Current state and append-only events are separate models.
- Local-first deployment; no mandatory cloud dependency.
- Separate human, agent and probe trust domains.
- Network discovery is bounded to operator-authorized scopes.
- Service inventory uses an explicit port allowlist and connect-only checks.
- LLDP/CDP physical topology is preferred; segment inference is retained only as an explicitly approximate fallback.
- Controlled remote operations use a strict allowlist and never expose generic shell execution.
- CI, security scanning, SBOM and observability are product concerns.

## Repository

| Area | Technology | Purpose |
|---|---|---|
| `backend/` | Python, FastAPI | API, ingestion, domain/application layers |
| `web/` | React, TypeScript | operator dashboard and control plane |
| `agents/windows/` | C#/.NET | Windows host agent |
| `agents/linux/` | Python | Linux host agent |
| `agents/macos/` | Swift | native macOS host agent |
| `agents/probe/` | Python | bounded discovery and distributed synthetic probe |
| `mobile/android/` | Kotlin, Compose | native Android operator client |
| `mobile/ios/` | Swift, SwiftUI | native iOS operator client |
| `firmware/esp32/` | C, ESP-IDF | ESP32 edge-probe workstream; production hardware acceptance pending |
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

See [Network Probe operations](docs/operations/NETWORK_PROBE.md) and [V1.3 distributed probes](docs/v1.3-distributed-probes-incidents.md).

## Protocol v1

The machine-readable contracts in `protocol/schemas/` define heartbeat, telemetry, events and an intentionally restricted command allowlist. Fixtures under `protocol/fixtures/` are intended to be consumed by every maintained language implementation.

## Release target

The platform is not considered production-ready until the complete acceptance path is proven from a clean deployment: migrations, operator/agent trust, discovery, host telemetry, realtime state, alert/incident lifecycle, durable recovery, backup/restore, operational health, load baselines and reproducible release artifacts.

See [ROADMAP.md](ROADMAP.md), [architecture](docs/architecture/ARCHITECTURE.md), [requirements](docs/product/REQUIREMENTS.md), [threat model](docs/security/THREAT_MODEL.md) and [ADRs](docs/adr/).
