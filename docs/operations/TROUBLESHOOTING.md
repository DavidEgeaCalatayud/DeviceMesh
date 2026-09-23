# Troubleshooting

Check services in this order: PostgreSQL -> Redis -> API readiness -> web/API connectivity -> agent enrollment -> telemetry ingestion -> realtime delivery. Use correlation IDs when following a request across boundaries.
