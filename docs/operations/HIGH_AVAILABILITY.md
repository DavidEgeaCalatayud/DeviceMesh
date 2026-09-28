# High availability

DeviceMesh V1 supports horizontal availability at the application tier. PostgreSQL and Redis remain external infrastructure dependencies and must be deployed with their own HA strategy when the installation requires database/cache failover.

## API tier

API instances are stateless with respect to durable product state. They share PostgreSQL for durable state and Redis for cross-instance realtime fan-out. Multiple API replicas can therefore serve the same deployment behind a reverse proxy/load balancer.

The repository includes a dedicated HA acceptance workflow that starts **two production API replicas** from `docker-compose.prod.yml` and places a Caddy reverse proxy in front of both. The workflow is part of pull-request validation whenever backend, production networking/proxy configuration, or the HA acceptance harness changes. Acceptance proves that:

- both replicas answer readiness independently;
- a service created through replica A is immediately readable through replica B, demonstrating shared durable state;
- round-robin traffic reaches both replicas through the load balancer;
- a WebSocket attached to replica B receives an event produced by an authenticated heartbeat sent to replica A, demonstrating cross-process Redis fan-out;
- disconnecting replica A from the Compose network leaves the load-balanced endpoint healthy through replica B;
- reconnecting the partitioned replica restores readiness and cross-instance realtime fan-out.

This is an application-tier acceptance test. It intentionally does not claim automatic failover for PostgreSQL, Redis, DNS or the host itself.

## Worker tier

Multiple worker processes may be started, but exactly one owns scheduled work at a time. Scheduler leadership uses the PostgreSQL session-level advisory lock `684291017`.

- the first worker that acquires the lock becomes scheduler leader;
- standby workers do not execute the leader-owned scheduler;
- the advisory lock belongs to the PostgreSQL session rather than process memory;
- if the leader process or database connection dies, PostgreSQL releases the lock automatically;
- a standby retries and may acquire leadership without a manual lease cleanup;
- graceful shutdown also releases the lock explicitly.

The integration suite opens independent PostgreSQL sessions, proves that only one can acquire scheduler leadership, invalidates the leader session to model an ungraceful process loss, and verifies that the standby can then acquire the lock.

## Realtime events

Production uses Redis as the event backend. API replicas consume the shared event stream and can fan out events to their connected WebSocket clients. This prevents realtime delivery from being tied to the process that produced the event. The HA acceptance workflow validates that property across two independent Uvicorn processes, including after a simulated replica network partition and recovery.

## Failure-domain boundary

This V1 guarantee covers DeviceMesh application processes:

- API replica or API-network-path loss can be absorbed by another healthy API replica behind the load balancer.
- A recovered API replica can rejoin shared PostgreSQL state and Redis realtime delivery.
- Worker leader loss can be absorbed by a standby worker.
- Realtime events are shared through Redis rather than an in-process-only bus.

It does **not** claim that a single PostgreSQL server, a single Redis server, the reverse proxy, DNS, storage or the host itself are highly available. Operators requiring end-to-end HA must provide redundant infrastructure for those dependencies.
