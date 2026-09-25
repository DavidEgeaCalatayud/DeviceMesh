from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


@dataclass(slots=True)
class AgentCredential:
    agent_id: str
    credential_id: str
    credential: str


@dataclass(slots=True)
class RequestSample:
    kind: str
    latency_ms: float
    status: int
    ok: bool


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def summary(samples: list[RequestSample]) -> dict[str, Any]:
    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if not sample.ok]
    return {
        "requests": len(samples),
        "failures": len(failures),
        "failureRate": (len(failures) / len(samples)) if samples else 0.0,
        "latencyMs": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
            "max": max(latencies, default=0.0),
        },
        "statusCounts": {
            str(status): sum(1 for sample in samples if sample.status == status)
            for status in sorted({sample.status for sample in samples})
        },
    }


def auth_headers(agent: AgentCredential) -> dict[str, str]:
    return {
        "Authorization": f"Agent {agent.credential}",
        "X-DeviceMesh-Agent-ID": agent.agent_id,
        "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
        "X-DeviceMesh-Nonce": uuid4().hex,
    }


async def bootstrap_agent(client: httpx.AsyncClient, operator_token: str, index: int, prefix: str) -> AgentCredential:
    headers = {"Authorization": f"Bearer {operator_token}"}
    issued = await client.post(
        "/api/v1/operator/agent-enrollment-tokens",
        headers=headers,
        json={"ttlSeconds": 900},
    )
    issued.raise_for_status()
    agent_id = f"{prefix}-{index:05d}"
    enrolled = await client.post(
        "/api/v1/agents/enroll",
        json={"token": issued.json()["token"], "agentId": agent_id},
    )
    enrolled.raise_for_status()
    payload = enrolled.json()
    return AgentCredential(agent_id, payload["credentialId"], payload["credential"])


async def bootstrap_agents(
    client: httpx.AsyncClient,
    operator_token: str,
    devices: int,
    concurrency: int,
    prefix: str,
) -> list[AgentCredential]:
    semaphore = asyncio.Semaphore(concurrency)

    async def create(index: int) -> AgentCredential:
        async with semaphore:
            return await bootstrap_agent(client, operator_token, index, prefix)

    return list(await asyncio.gather(*(create(index) for index in range(devices))))


def load_cache(path: Path, devices: int, prefix: str) -> list[AgentCredential] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("agents", [])
    agents = [AgentCredential(**row) for row in rows]
    if len(agents) != devices or any(not agent.agent_id.startswith(prefix + "-") for agent in agents):
        return None
    return agents


def save_cache(path: Path, agents: list[AgentCredential]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"agents": [asdict(agent) for agent in agents]}, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


async def request_sample(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    kind: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> RequestSample:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, headers=headers, json=payload)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return RequestSample(kind, latency_ms, response.status_code, response.is_success)
    except httpx.HTTPError:
        return RequestSample(kind, (time.perf_counter() - started) * 1000.0, 0, False)


async def exercise_agent(client: httpx.AsyncClient, agent: AgentCredential) -> list[RequestSample]:
    timestamp = datetime.now(UTC).isoformat()
    heartbeat = {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": agent.agent_id,
        "timestamp": timestamp,
        "device": {
            "hostname": agent.agent_id,
            "operatingSystem": "benchmark",
            "operatingSystemVersion": "1",
            "architecture": "x86_64",
            "manufacturer": "DeviceMesh",
            "ipAddresses": [],
            "macAddresses": [],
        },
    }
    telemetry = {
        "type": "telemetry",
        "protocolVersion": 1,
        "agentId": agent.agent_id,
        "timestamp": timestamp,
        "metrics": [
            {"name": "cpu.usage", "value": random.uniform(1.0, 95.0), "unit": "percent"},
            {"name": "memory.usage", "value": random.uniform(10.0, 90.0), "unit": "percent"},
            {"name": "disk.usage", "value": random.uniform(5.0, 85.0), "unit": "percent"},
        ],
    }
    heartbeat_sample = await request_sample(
        client, "POST", "/api/v1/agents/heartbeat", "heartbeat",
        headers=auth_headers(agent), payload=heartbeat,
    )
    telemetry_sample = await request_sample(
        client, "POST", "/api/v1/agents/telemetry", "telemetry",
        headers=auth_headers(agent), payload=telemetry,
    )
    return [heartbeat_sample, telemetry_sample]


async def run_round(
    client: httpx.AsyncClient,
    agents: list[AgentCredential],
    concurrency: int,
) -> list[RequestSample]:
    semaphore = asyncio.Semaphore(concurrency)

    async def execute(agent: AgentCredential) -> list[RequestSample]:
        async with semaphore:
            return await exercise_agent(client, agent)

    nested = await asyncio.gather(*(execute(agent) for agent in agents))
    return [sample for pair in nested for sample in pair]


async def fetch_metrics(client: httpx.AsyncClient, operator_token: str) -> str:
    response = await client.get("/metrics", headers={"Authorization": f"Bearer {operator_token}"})
    response.raise_for_status()
    return response.text


async def cleanup_agents(client: httpx.AsyncClient, operator_token: str, agents: list[AgentCredential]) -> None:
    headers = {"Authorization": f"Bearer {operator_token}"}
    for agent in agents:
        response = await client.delete(
            f"/api/v1/operator/agents/{agent.agent_id}/credentials/{agent.credential_id}",
            headers=headers,
        )
        if response.status_code not in {204, 404}:
            response.raise_for_status()


async def async_main(args: argparse.Namespace) -> int:
    operator_token = args.operator_token or os.getenv("DEVICEMESH_OPERATOR_TOKEN")
    if not operator_token:
        raise SystemExit("set --operator-token or DEVICEMESH_OPERATOR_TOKEN")

    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=max(args.concurrency * 2, 20), max_keepalive_connections=max(args.concurrency, 10))
    async with httpx.AsyncClient(base_url=args.server.rstrip("/"), timeout=timeout, limits=limits) as client:
        cache_path = Path(args.credential_cache) if args.credential_cache else None
        agents = load_cache(cache_path, args.devices, args.prefix) if cache_path else None
        bootstrap_started = time.perf_counter()
        if agents is None:
            agents = await bootstrap_agents(client, operator_token, args.devices, args.concurrency, args.prefix)
            if cache_path:
                save_cache(cache_path, agents)
        bootstrap_seconds = time.perf_counter() - bootstrap_started

        before_metrics = await fetch_metrics(client, operator_token)
        started = time.perf_counter()
        all_samples: list[RequestSample] = []
        rounds = 0
        deadline = started + args.duration_seconds if args.duration_seconds else None
        while True:
            round_started = time.perf_counter()
            all_samples.extend(await run_round(client, agents, args.concurrency))
            rounds += 1
            if deadline is None and rounds >= args.rounds:
                break
            if deadline is not None and time.perf_counter() >= deadline:
                break
            sleep_for = max(0.0, args.interval_seconds - (time.perf_counter() - round_started))
            if sleep_for:
                await asyncio.sleep(sleep_for)

        elapsed = time.perf_counter() - started
        after_metrics = await fetch_metrics(client, operator_token)
        report = {
            "generatedAt": datetime.now(UTC).isoformat(),
            "server": args.server,
            "devices": args.devices,
            "rounds": rounds,
            "concurrency": args.concurrency,
            "durationSeconds": elapsed,
            "bootstrapSeconds": bootstrap_seconds,
            "requestsPerSecond": len(all_samples) / elapsed if elapsed else 0.0,
            "overall": summary(all_samples),
            "heartbeat": summary([sample for sample in all_samples if sample.kind == "heartbeat"]),
            "telemetry": summary([sample for sample in all_samples if sample.kind == "telemetry"]),
        }
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            output.with_suffix(output.suffix + ".metrics.before.prom").write_text(before_metrics, encoding="utf-8")
            output.with_suffix(output.suffix + ".metrics.after.prom").write_text(after_metrics, encoding="utf-8")
        print(json.dumps(report, indent=2))

        if args.cleanup:
            await cleanup_agents(client, operator_token, agents)
            if cache_path:
                cache_path.unlink(missing_ok=True)

        failure_rate = report["overall"]["failureRate"]
        p95 = report["overall"]["latencyMs"]["p95"]
        if failure_rate > args.max_failure_rate or p95 > args.max_p95_ms:
            print(
                f"acceptance failed: failure_rate={failure_rate:.4f} (max {args.max_failure_rate:.4f}), "
                f"p95={p95:.2f}ms (max {args.max_p95_ms:.2f}ms)"
            )
            return 2
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark DeviceMesh authenticated heartbeat/telemetry ingestion")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--operator-token")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--prefix", default="bench")
    parser.add_argument("--credential-cache")
    parser.add_argument("--output")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--max-failure-rate", type=float, default=0.001)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    args = parser.parse_args()
    if not 1 <= args.devices <= 10_000:
        parser.error("--devices must be between 1 and 10000")
    if not 1 <= args.concurrency <= 1000:
        parser.error("--concurrency must be between 1 and 1000")
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    if args.duration_seconds < 0 or args.interval_seconds < 0:
        parser.error("durations cannot be negative")
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
