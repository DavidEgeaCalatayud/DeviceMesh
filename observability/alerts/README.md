# Platform Alerts

Operational alerts for DeviceMesh itself are separate from user-configured device and service alerts. Prometheus evaluates the rules in `platform.rules.yml` every 15 seconds in the production stack.

## Covered failure modes

- API scrape unavailable for two minutes.
- Independent scheduler worker scrape unavailable for two minutes.
- Worker reachable but no scheduler advisory-lock leader is active.
- Synthetic scheduling, offline-device sweeps or retention enforcement stop making progress.
- HTTP 5xx ratio remains above 5% while the API is receiving traffic.
- HTTP request p95 remains above one second.
- Database query p95 remains above 500 ms.

The rule file also exposes recording rules for HTTP error ratio, HTTP p95 and database-query p95 so dashboards and future notification routing can reuse one canonical calculation.

These are **platform-health evaluations** only. Delivery to email, chat, paging or other destinations belongs to the separate notification/routing feature and is intentionally not coupled to Prometheus rule evaluation.

## Validation

`production-acceptance.yml` starts the real production Compose services, waits until both API and worker scrape targets are healthy, queries Prometheus `/api/v1/rules`, and requires the core DeviceMesh rule set to be loaded. The same acceptance run verifies at least two automatically provisioned Grafana dashboards.
