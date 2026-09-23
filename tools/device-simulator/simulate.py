from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic DeviceMesh agents for development")
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--devices", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.devices <= 10_000:
        raise SystemExit("--devices must be between 1 and 10000")

    with httpx.Client(base_url=args.server, timeout=10) as client:
        for index in range(args.devices):
            agent_id = f"sim-{index:05d}"
            timestamp = datetime.now(UTC).isoformat()
            client.post("/api/v1/agents/heartbeat", json={"type":"heartbeat","protocolVersion":1,"agentId":agent_id,"timestamp":timestamp}).raise_for_status()
            client.post("/api/v1/agents/telemetry", json={"type":"telemetry","protocolVersion":1,"agentId":agent_id,"timestamp":timestamp,"metrics":[{"name":"cpu.usage","value":random.uniform(1,100),"unit":"percent"},{"name":"memory.usage","value":random.uniform(10,95),"unit":"percent"}]}).raise_for_status()
    print(f"published {args.devices} synthetic devices")


if __name__ == "__main__": main()
