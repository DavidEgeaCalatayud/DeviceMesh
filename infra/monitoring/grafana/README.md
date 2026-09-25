# Grafana

DeviceMesh provisions Grafana automatically in the production Compose stack.

## Provisioned resources

- Prometheus datasource: `DeviceMesh Prometheus` (`http://prometheus:9090`).
- `DeviceMesh / Overview`: fleet, HTTP, ingestion, WebSocket, database and incident signals.
- `DeviceMesh / Workers & Synthetics`: scheduler leadership, last-success age, probe availability and job outcomes.

Grafana listens only on `127.0.0.1:3000` by default so it is not exposed directly to the Internet. Use an SSH tunnel or place it behind an authenticated reverse proxy if remote access is required.

The administrator password is generated during `tools/deployment/config.py --init-secrets` and stored in `.secrets/grafana_admin_password`. Existing installations are upgraded safely by generating only the new Grafana credential while retaining their current DeviceMesh/PostgreSQL secrets.

Prometheus authenticates to the protected API `/metrics` endpoint with the existing operator credential and scrapes the independent worker metrics listener on the private Compose network.
