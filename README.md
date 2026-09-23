# DeviceMesh

DeviceMesh is a local-first device observability and management platform for discovering, monitoring and understanding devices across a network.

> Status: engineering foundation / V1 bootstrap.

The project is designed as a production-style monorepo spanning a FastAPI backend, React/TypeScript web client, .NET Windows agent, Android and iOS clients, an ESP32 probe, a versioned agent protocol, PostgreSQL, Docker and automated quality/security gates.

## V1 scope

- FastAPI backend and PostgreSQL persistence
- LAN device discovery and identity resolution
- Windows agent enrollment, heartbeat and telemetry
- Realtime device state via WebSockets
- Device event timeline and threshold alerts
- React/TypeScript dashboard
- Docker Compose local deployment
- Unit, integration, contract and E2E testing foundations
- Authentication and agent trust model

## Architecture principles

- Domain logic is independent of frameworks and transport details.
- Device identity is not reduced to an IP address.
- Agent/server communication is explicitly versioned and contract-tested.
- Current device state and append-only events are modeled separately.
- Local-first deployment is the default; cloud connectivity is optional.
- Security, observability and reproducibility are first-class concerns.

Detailed architecture, ADRs, protocol contracts and implementation code are being bootstrapped in the repository.
