from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def run(command: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(command, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run resumable DeviceMesh soak chunks with PostgreSQL capacity snapshots"
    )
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--chunk-minutes", type=float, default=15.0)
    parser.add_argument("--devices", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", default="artifacts/soak")
    parser.add_argument("--operator-token", default=os.getenv("DEVICEMESH_OPERATOR_TOKEN"))
    parser.add_argument("--database-url", default=os.getenv("DEVICEMESH_DATABASE_URL"))
    parser.add_argument("--api-metrics-url", default=os.getenv("DEVICEMESH_API_METRICS_URL"))
    parser.add_argument("--worker-metrics-url", default=os.getenv("DEVICEMESH_WORKER_METRICS_URL"))
    parser.add_argument("--redis-url", default=os.getenv("DEVICEMESH_REDIS_URL"))
    parser.add_argument("--websocket-url", default=os.getenv("DEVICEMESH_WEBSOCKET_URL"))
    parser.add_argument("--max-failure-rate", type=float, default=0.001)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    args = parser.parse_args()
    if not 0 < args.duration_hours <= 48:
        parser.error("--duration-hours must be > 0 and <= 48")
    if not 1 <= args.devices <= 10_000:
        parser.error("--devices must be between 1 and 10000")
    if not args.operator_token:
        parser.error("operator token is required")
    if not args.database_url:
        parser.error("database URL is required")
    if not args.api_metrics_url:
        parser.error("API metrics URL is required")
    if not args.worker_metrics_url:
        parser.error("worker metrics URL is required")
    if not args.redis_url:
        parser.error("Redis URL is required")
    if not args.websocket_url:
        parser.error("WebSocket URL is required")

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    credential_cache = output / "agents.json"
    state_path = output / "state.json"
    elapsed_before = 0.0
    chunk_index = 0
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        elapsed_before = float(previous.get("elapsedSeconds", 0.0))
        chunk_index = int(previous.get("chunks", 0))

    target_seconds = args.duration_hours * 3600.0
    chunk_seconds = args.chunk_minutes * 60.0
    env = dict(os.environ)
    env["DEVICEMESH_OPERATOR_TOKEN"] = args.operator_token
    env["DEVICEMESH_DATABASE_URL"] = args.database_url
    started = time.monotonic()

    while elapsed_before + (time.monotonic() - started) < target_seconds:
        remaining = target_seconds - elapsed_before - (time.monotonic() - started)
        current_chunk = min(chunk_seconds, remaining)
        stamp = f"{chunk_index:05d}"
        load_report = output / f"load-{stamp}.json"
        capacity_report = output / f"capacity-{stamp}.json"
        runtime_report = output / f"runtime-{stamp}.json"
        run(
            [
                sys.executable,
                "tools/benchmarking/load_test.py",
                "--server",
                args.server,
                "--devices",
                str(args.devices),
                "--concurrency",
                str(args.concurrency),
                "--duration-seconds",
                str(current_chunk),
                "--interval-seconds",
                str(args.interval_seconds),
                "--credential-cache",
                str(credential_cache),
                "--output",
                str(load_report),
                "--max-failure-rate",
                str(args.max_failure_rate),
                "--max-p95-ms",
                str(args.max_p95_ms),
            ],
            env=env,
        )
        run(
            [
                sys.executable,
                "tools/benchmarking/capacity_report.py",
                "--database-url",
                args.database_url,
                "--output",
                str(capacity_report),
            ],
            env=env,
        )
        run(
            [
                sys.executable,
                "tools/benchmarking/runtime_snapshot.py",
                "--api-metrics-url",
                args.api_metrics_url,
                "--worker-metrics-url",
                args.worker_metrics_url,
                "--redis-url",
                args.redis_url,
                "--websocket-url",
                args.websocket_url,
                "--operator-token",
                args.operator_token,
                "--output",
                str(runtime_report),
            ],
            env=env,
        )
        chunk_index += 1
        elapsed = elapsed_before + (time.monotonic() - started)
        state_path.write_text(
            json.dumps(
                {
                    "updatedAt": datetime.now(UTC).isoformat(),
                    "elapsedSeconds": elapsed,
                    "targetSeconds": target_seconds,
                    "chunks": chunk_index,
                    "devices": args.devices,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    summary_path = output / "capacity-summary.json"
    run(
        [
            sys.executable,
            "tools/benchmarking/capacity_summary.py",
            str(output),
            "--output",
            str(summary_path),
        ],
        env=env,
    )
    print(state_path.read_text(encoding="utf-8"))
    print(summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
