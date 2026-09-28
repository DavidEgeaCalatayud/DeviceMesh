from __future__ import annotations

import asyncio
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import httpx

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.outbox import ResultOutbox


def _agent_version() -> str:
    try:
        return version("devicemesh-probe")
    except PackageNotFoundError:
        return "0.2.0-dev"


def _queue_snapshot(config: ProbeConfig) -> tuple[int, int]:
    outbox = ResultOutbox(Path(config.result_queue_path))
    try:
        return outbox.count(), outbox.capacity
    finally:
        outbox.close()


async def publish_runtime_telemetry(
    config: ProbeConfig,
    *,
    started_at: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    token = config.require_synthetic_token()
    queue_depth, queue_capacity = await asyncio.to_thread(_queue_snapshot, config)
    payload = {
        "agentVersion": _agent_version(),
        "uptimeSeconds": max(0, int(time.monotonic() - started_at)),
        "queueDepth": queue_depth,
        "queueCapacity": queue_capacity,
        "maxConcurrentChecks": config.max_concurrent_checks,
    }
    async with httpx.AsyncClient(
        transport=transport,
        base_url=config.server_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(20.0),
    ) as client:
        response = await client.post("/api/v1/probes/runtime-heartbeat", json=payload)
        response.raise_for_status()


async def maintain_runtime_telemetry(config: ProbeConfig, *, started_at: float) -> None:
    interval = max(15.0, min(60.0, float(config.synthetic_poll_seconds)))
    while True:
        try:
            await publish_runtime_telemetry(config, started_at=started_at)
        except httpx.HTTPError as exc:
            # Runtime telemetry must never stop the synthetic work loop.
            print(f"probe runtime telemetry unavailable: {type(exc).__name__}")
        await asyncio.sleep(interval)
