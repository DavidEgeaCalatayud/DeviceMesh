#!/usr/bin/env python3
"""Descriptive acceptance harness against an isolated, already running test stack."""
import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

import httpx
import websockets


async def run(base: str, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=base, timeout=20) as client:
        ready = await client.get("/ready")
        ready.raise_for_status()
        assert (await client.get("/api/v1/devices")).status_code == 401
        service = await client.post("/api/v1/service-catalog", headers=headers, json={"name": "acceptance-canary"})
        service.raise_for_status()
        agent_id = f"acceptance-{uuid4().hex}"
        enrollment = await client.post("/api/v1/operator/agent-enrollment-tokens", headers=headers, json={})
        enrollment.raise_for_status()
        credentials = await client.post("/api/v1/agents/enroll", json={"token": enrollment.json()["token"], "agentId": agent_id})
        credentials.raise_for_status()
        def agent_headers() -> dict[str, str]:
            return {"Authorization": f"Agent {credentials.json()['credential']}",
                    "X-DeviceMesh-Agent-ID": agent_id, "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
                    "X-DeviceMesh-Nonce": uuid4().hex}
        async with websockets.connect(base.replace("http", "ws", 1) + "/ws/events") as socket:
            await socket.send(json.dumps({"token": token}))
            # Allow the authenticated subscription to be registered before publishing.
            await asyncio.sleep(0.2)
            heartbeat = await client.post("/api/v1/agents/heartbeat", headers=agent_headers(), json={
                "type": "heartbeat", "protocolVersion": 1, "agentId": agent_id,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            heartbeat.raise_for_status()
            async with asyncio.timeout(15):
                while True:
                    event = json.loads(await socket.recv())
                    if event.get("payload", {}).get("deviceId") == agent_id:
                        break
        inventory = await client.get("/api/v1/devices", headers=headers)
        inventory.raise_for_status()
        assert any(device["id"] == agent_id for device in inventory.json())
        print(json.dumps({"status": "passed", "agentId": agent_id, "serviceId": service.json()["id"],
                          "checks": ["ready", "private-reads", "enrollment", "heartbeat", "redis-websocket", "inventory"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.token_file.read_text().strip()))
