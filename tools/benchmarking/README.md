# Benchmarking

DeviceMesh includes an authenticated ingestion benchmark that exercises the same enrollment, heartbeat and telemetry paths used by real agents against the production Docker stack.

## CI performance gate

`.github/workflows/performance.yml` runs the production API/worker stack with PostgreSQL and Redis and executes three scales in sequence:

- 10 agents
- 100 agents
- 1,000 agents

Every simulated agent obtains a one-time enrollment token, enrolls for an agent credential, then publishes one authenticated heartbeat and one telemetry batch containing CPU, memory and network-latency metrics.

The benchmark records ingestion-only latency and reports:

- total requests and errors;
- duration;
- requests/second;
- P50, P95, P99 and maximum HTTP latency.

CI currently fails on any ingestion error, P95 above 3,000 ms, or throughput below 10 requests/second. These thresholds are deliberately conservative for shared GitHub-hosted runners; historical numbers should be compared using the uploaded `performance-results` artifact instead of treating runner timing as a hardware benchmark.

## Local run

Start the production stack with the API exposed on localhost and run:

```bash
python tools/benchmarking/load.py \
  --server http://127.0.0.1:18000 \
  --token-file .secrets/operator_token \
  --scales 10 100 1000 \
  --concurrency 32 \
  --output benchmark-results.json
```

Use dedicated hardware and longer soak tests when evaluating capacity planning. The CI gate answers a narrower question: whether a normal change causes an obvious regression in authenticated V1 ingestion at the supported small/medium deployment scales.
