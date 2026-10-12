from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis
import websockets


def _metric(text: str, name: str) -> float | None:
    prefix = name + " "
    for line in text.splitlines():
        if line.startswith(prefix):
            try:
                return float(line[len(prefix):].strip())
            except ValueError:
                return None
    return None


async def _websocket_reconnects(url: str, token: str, attempts: int) -> dict[str, Any]:
    successes = 0
    failures: list[str] = []
    for _ in range(attempts):
        try:
            async with websockets.connect(
                url,
                open_timeout=5,
                close_timeout=5,
                ping_interval=None,
                max_size=1_048_576,
            ) as socket:
                await socket.send(json.dumps({"token": token}))
                await socket.send("soak-heartbeat")
                await asyncio.sleep(0.05)
                successes += 1
        except Exception as exc:  # evidence tool: preserve error class, never token/content
            failures.append(type(exc).__name__)
    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "successRate": successes / attempts if attempts else 1.0,
    }


def _http_metrics(url: str, token: str | None = None) -> dict[str, float | None]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(timeout=10) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        body = response.text
    names = (
        "process_resident_memory_bytes",
        "process_virtual_memory_bytes",
        "process_open_fds",
        "devicemesh_ws_connections",
        "devicemesh_worker_leader",
    )
    return {name: _metric(body, name) for name in names}


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture DeviceMesh runtime soak evidence")
    parser.add_argument("--api-metrics-url", required=True)
    parser.add_argument("--worker-metrics-url", required=True)
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--websocket-url", required=True)
    parser.add_argument("--operator-token", default=os.getenv("DEVICEMESH_OPERATOR_TOKEN"))
    parser.add_argument("--websocket-attempts", type=int, default=3)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.operator_token:
        parser.error("operator token is required")
    if not 1 <= args.websocket_attempts <= 20:
        parser.error("--websocket-attempts must be between 1 and 20")

    api_metrics = _http_metrics(args.api_metrics_url, args.operator_token)
    worker_metrics = _http_metrics(args.worker_metrics_url)

    client = redis.Redis.from_url(
        args.redis_url,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=True,
    )
    info = client.info()
    redis_evidence = {
        "usedMemoryBytes": int(info.get("used_memory", 0)),
        "usedMemoryPeakBytes": int(info.get("used_memory_peak", 0)),
        "maxMemoryBytes": int(info.get("maxmemory", 0)),
        "connectedClients": int(info.get("connected_clients", 0)),
        "blockedClients": int(info.get("blocked_clients", 0)),
        "evictedKeys": int(info.get("evicted_keys", 0)),
        "keyspaceHits": int(info.get("keyspace_hits", 0)),
        "keyspaceMisses": int(info.get("keyspace_misses", 0)),
    }
    websocket = asyncio.run(
        _websocket_reconnects(
            args.websocket_url,
            args.operator_token,
            args.websocket_attempts,
        )
    )

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "api": api_metrics,
        "worker": worker_metrics,
        "redis": redis_evidence,
        "websocketReconnect": websocket,
    }
    payload = json.dumps(report, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
