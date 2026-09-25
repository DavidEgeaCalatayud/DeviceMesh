# Benchmarking

DeviceMesh keeps performance acceptance reproducible instead of relying on one-off local measurements.

`load_test.py` exercises the real authenticated Agent Protocol v1 path: it provisions disposable agent credentials through the administrator API and then sends heartbeat + telemetry batches with unique replay-protection nonces. The report contains request throughput, failure rate and mean/P50/P95/P99/max latency, split by heartbeat and telemetry. Prometheus snapshots are captured before and after the run so server/process/database-facing counters can be correlated with the client results.

## Scale gates

Run the canonical scale points against a production-format deployment:

```bash
export DEVICEMESH_OPERATOR_TOKEN="$(cat .secrets/operator_token)"
python tools/benchmarking/load_test.py --server http://127.0.0.1:18000 --devices 10 --rounds 5 --cleanup --output artifacts/benchmark-10.json
python tools/benchmarking/load_test.py --server http://127.0.0.1:18000 --devices 100 --rounds 5 --cleanup --output artifacts/benchmark-100.json
python tools/benchmarking/load_test.py --server http://127.0.0.1:18000 --devices 1000 --rounds 5 --cleanup --output artifacts/benchmark-1000.json
```

The default acceptance gate is <= 0.1% failed requests and <= 1000 ms P95. Those defaults are deliberately conservative for heterogeneous self-hosted hardware; tighten them only after recording the target host profile. Override them with `--max-failure-rate` and `--max-p95-ms`.

## Soak runs

A soak uses the same executable and can persist credentials so provisioning is not mixed into the steady-state workload:

```bash
python tools/benchmarking/load_test.py \
  --server https://mesh.example.com \
  --devices 1000 \
  --concurrency 100 \
  --duration-seconds 86400 \
  --interval-seconds 30 \
  --credential-cache .local/benchmark-agents.json \
  --output artifacts/soak-1000-24h.json
```

The credential cache contains live agent secrets and is written mode `0600` when the platform supports POSIX permissions. Keep it outside source control and delete/revoke it after the run. Use `--cleanup` for disposable CI runs.

For a 24 h or 48 h acceptance report, preserve:

- the JSON client report;
- the `.metrics.before.prom` and `.metrics.after.prom` snapshots;
- `docker stats --no-stream` at the start/end and periodically during the run;
- PostgreSQL database size and row counts for `metric_samples`, rollups and event tables;
- host CPU/RAM/disk model and Docker/OS versions.

Do not claim a 10/100/1000 or 24/48 h result from the existence of this harness alone. The measured report is the evidence.
