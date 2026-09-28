#!/usr/bin/env python3
"""Acceptance checks that require two live DeviceMesh API replicas."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import websockets


async def _ready(client: httpx.AsyncClient) -> None:
    response = await client.get("/ready")
    response.raise_for_status()


async def run(api_a: str, api_b: str, balanced: str, token: str) -> None:
    human_headers = {"Authorization": f"Bearer {token}"}
    async with (
        httpx.AsyncClient(base_url=api_a, timeout=20) as first,
        httpx.AsyncClient(base_url=api_b, timeout=20) as second,
        httpx.AsyncClient(base_url=balanced, timeout=20) as lb,
    ):
        await _ready(first)
        await _ready(second)
        await _ready(lb)

        # Durable application state written through one process must immediately
        # be visible through another process sharing PostgreSQL.
        service_name = f"ha-canary-{uuid4().hex[:12]}"
        created = await first.post(
            "/api/v1/service-catalog",
            headers=human_headers,
            json={"name": service_name},
        )
        created.raise_for_status()
        inventory = await second.get("/api/v1/service-catalog", headers=human_headers)
        inventory.raise_for_status()
        assert any(item["id"] == created.json()["id"] for item in inventory.json())

        # The load balancer must actively use both replicas before failure is
        # injected. HAProxy stamps the selected backend server into this header.
        upstreams: set[str] = set()
        for _ in range(12):
            response = await lb.get("/ready")
            response.raise_for_status()
            upstream = response.headers.get("x-devicemesh-upstream")
            if upstream:
                upstreams.add(upstream)
        assert len(upstreams) == 2, f"load balancer did not reach both replicas: {upstreams}"

        # Create an authenticated agent through replica A, subscribe to replica B,
        # and publish the event through A. Receipt on B proves Redis fan-out is
        # cross-process rather than an in-memory artifact.
        agent_id = f"ha-agent-{uuid4().hex}"
        enrollment = await first.post(
            "/api/v1/operator/agent-enrollment-tokens",
            headers=human_headers,
            json={},
        )
        enrollment.raise_for_status()
        enrolled = await first.post(
            "/api/v1/agents/enroll",
            json={"token": enrollment.json()["token"], "agentId": agent_id},
        )
        enrolled.raise_for_status()
        credential = enrolled.json()["credential"]

        def agent_headers() -> dict[str, str]:
            return {
                "Authorization": f"Agent {credential}",
                "X-DeviceMesh-Agent-ID": agent_id,
                "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
                "X-DeviceMesh-Nonce": uuid4().hex,
            }

        ws_url = api_b.replace("http://", "ws://", 1) + "/ws/events"
        async with websockets.connect(ws_url) as socket:
            await socket.send(json.dumps({"token": token}))
            await asyncio.sleep(0.3)
            heartbeat = await first.post(
                "/api/v1/agents/heartbeat",
                headers=agent_headers(),
                json={
                    "type": "heartbeat",
                    "protocolVersion": 1,
                    "agentId": agent_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            heartbeat.raise_for_status()
            async with asyncio.timeout(15):
                while True:
                    event = json.loads(await socket.recv())
                    if event.get("payload", {}).get("deviceId") == agent_id:
                        break

        devices = await second.get("/api/v1/devices", headers=human_headers)
        devices.raise_for_status()
        assert any(device["id"] == agent_id for device in devices.json())

        print(
            json.dumps(
                {
                    "status": "passed",
                    "serviceId": created.json()["id"],
                    "agentId": agent_id,
                    "upstreams": sorted(upstreams),
                    "checks": [
                        "two-api-ready",
                        "shared-postgres",
                        "load-balanced-traffic",
                        "cross-instance-redis-websocket",
                    ],
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-a", required=True)
    parser.add_argument("--api-b", required=True)
    parser.add_argument("--balanced", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(
        run(
            args.api_a,
            args.api_b,
            args.balanced,
            args.token_file.read_text(encoding="utf-8").strip(),
        )
    )
