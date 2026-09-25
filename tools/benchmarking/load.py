from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


@dataclass(frozen=True, slots=True)
class AgentCredential:
    agent_id: str
    credential: str


@dataclass(frozen=True, slots=True)
class ScaleResult:
    devices: int
    requests: int
    errors: int
    duration_seconds: float
    requests_per_second: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[rank]


def agent_headers(agent: AgentCredential) -> dict[str, str]:
    return {
        "Authorization": f"Agent {agent.credential}",
        "X-DeviceMesh-Agent-ID": agent.agent_id,
        "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
        "X-DeviceMesh-Nonce": uuid4().hex,
    }


async def enroll_agents(
    client: httpx.AsyncClient,
    operator_token: str,
    count: int,
    concurrency: int,
    prefix: str,
) -> list[AgentCredential]:
    semaphore = asyncio.Semaphore(concurrency)

    async def enroll(index: int) -> AgentCredential:
        async with semaphore:
            token_response = await client.post(
                "/api/v1/operator/agent-enrollment-tokens",
                headers={"Authorization": f"Bearer {operator_token}"},
                json={},
            )
            token_response.raise_for_status()
            agent_id = f"{prefix}-{index:05d}"
            enrollment = await client.post(
                "/api/v1/agents/enroll",
                json={"token": token_response.json()["token"], "agentId": agent_id},
            )
            enrollment.raise_for_status()
            return AgentCredential(agent_id=agent_id, credential=enrollment.json()["credential"])

    return list(await asyncio.gather(*(enroll(index) for index in range(count))))


async def benchmark_scale(
    client: httpx.AsyncClient,
    agents: list[AgentCredential],
    concurrency: int,
) -> ScaleResult:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors = 0
    latency_lock = asyncio.Lock()

    async def request(agent: AgentCredential, kind: str) -> None:
        nonlocal errors
        timestamp = datetime.now(UTC).isoformat()
        if kind == "heartbeat":
            path = "/api/v1/agents/heartbeat"
            payload = {
                "type": "heartbeat",
                "protocolVersion": 1,
                "agentId": agent.agent_id,
                "timestamp": timestamp,
            }
        else:
            path = "/api/v1/agents/telemetry"
            payload = {
                "type": "telemetry",
                "protocolVersion": 1,
                "agentId": agent.agent_id,
                "timestamp": timestamp,
                "metrics": [
                    {"name": "cpu.usage", "value": 42.0, "unit": "percent"},
                    {"name": "memory.usage", "value": 61.0, "unit": "percent"},
                    {"name": "network.latency.ms", "value": 18.0, "unit": "ms"},
                ],
            }
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.post(path, headers=agent_headers(agent), json=payload)
                response.raise_for_status()
            except httpx.HTTPError:
                async with latency_lock:
                    errors += 1
            finally:
                elapsed = (time.perf_counter() - started) * 1000.0
                async with latency_lock:
                    latencies.append(elapsed)

    started = time.perf_counter()
    await asyncio.gather(*(
        request(agent, kind)
        for agent in agents
        for kind in ("heartbeat", "telemetry")
    ))
    duration = time.perf_counter() - started
    request_count = len(agents) * 2
    return ScaleResult(
        devices=len(agents),
        requests=request_count,
        errors=errors,
        duration_seconds=round(duration, 3),
        requests_per_second=round(request_count / duration, 2) if duration else 0.0,
        p50_ms=round(percentile(latencies, 0.50), 2),
        p95_ms=round(percentile(latencies, 0.95), 2),
        p99_ms=round(percentile(latencies, 0.99), 2),
        max_ms=round(max(latencies, default=0.0), 2),
    )


async def run(args: argparse.Namespace) -> list[ScaleResult]:
    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("operator token file is empty")
    timeout = httpx.Timeout(args.timeout)
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    results: list[ScaleResult] = []
    async with httpx.AsyncClient(base_url=args.server.rstrip("/"), timeout=timeout, limits=limits) as client:
        for count in args.scales:
            prefix = f"bench-{count}-{uuid4().hex[:8]}"
            agents = await enroll_agents(client, token, count, args.concurrency, prefix)
            result = await benchmark_scale(client, agents, args.concurrency)
            results.append(result)
            print(json.dumps(asdict(result), sort_keys=True))
            if result.errors:
                raise SystemExit(f"benchmark produced {result.errors} failed ingestion request(s) at {count} devices")
            if result.p95_ms > args.max_p95_ms:
                raise SystemExit(f"p95 {result.p95_ms} ms exceeds {args.max_p95_ms} ms at {count} devices")
            if result.requests_per_second < args.min_rps:
                raise SystemExit(
                    f"throughput {result.requests_per_second} req/s is below {args.min_rps} req/s at {count} devices"
                )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Authenticated DeviceMesh ingestion benchmark")
    parser.add_argument("--server", default="http://127.0.0.1:18000")
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--scales", type=int, nargs="+", default=[10, 100, 1000])
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-p95-ms", type=float, default=3000.0)
    parser.add_argument("--min-rps", type=float, default=10.0)
    parser.add_argument("--output", default="benchmark-results.json")
    args = parser.parse_args()
    if not args.scales or any(scale < 1 or scale > 10_000 for scale in args.scales):
        raise SystemExit("all --scales values must be between 1 and 10000")
    if not 1 <= args.concurrency <= 256:
        raise SystemExit("--concurrency must be between 1 and 256")

    results = asyncio.run(run(args))
    output = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "server": args.server,
        "concurrency": args.concurrency,
        "thresholds": {"maxP95Ms": args.max_p95_ms, "minRequestsPerSecond": args.min_rps},
        "results": [asdict(result) for result in results],
        "summary": {
            "medianP95Ms": round(statistics.median(result.p95_ms for result in results), 2),
            "minimumRequestsPerSecond": min(result.requests_per_second for result in results),
        },
    }
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
