"""Experimental Linux agent adapter. Windows remains the V1 reference agent."""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime

import httpx
import psutil


def snapshot(agent_id: str) -> dict[str, object]:
    return {
        "type": "telemetry",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": [
            {"name": "cpu.usage", "value": psutil.cpu_percent(), "unit": "percent"},
            {"name": "memory.usage", "value": psutil.virtual_memory().percent, "unit": "percent"},
        ],
    }


def main() -> None:
    base_url = os.getenv("DEVICEMESH_SERVER", "http://localhost:8000")
    agent_id = os.getenv("DEVICEMESH_AGENT_ID", socket.gethostname())
    response = httpx.post(f"{base_url}/api/v1/agents/telemetry", json=snapshot(agent_id), timeout=10)
    response.raise_for_status()


if __name__ == "__main__":
    main()
