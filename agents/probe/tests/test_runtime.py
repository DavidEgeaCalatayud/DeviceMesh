import asyncio
import json
import time

import httpx

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.discovery import DiscoveryScope
from devicemesh_probe.outbox import ResultOutbox
from devicemesh_probe.runtime import publish_runtime_telemetry


def test_runtime_telemetry_reports_queue_and_concurrency(tmp_path) -> None:
    queue = tmp_path / "results.sqlite3"
    outbox = ResultOutbox(queue)
    try:
        outbox.enqueue(
            {
                "workId": "11111111-1111-1111-1111-111111111111",
                "checkedAt": "2026-09-28T08:00:00Z",
                "success": True,
                "latencyMs": 1.0,
                "httpStatus": 200,
                "errorKind": None,
                "error": None,
            }
        )
    finally:
        outbox.close()

    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/probes/runtime-heartbeat"
        assert request.headers["Authorization"] == "Bearer probe-token"
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"probeId": "probe-1"})

    config = ProbeConfig(
        server_url="https://mesh.example.test",
        source="test-probe",
        scopes=(DiscoveryScope("10.0.0.0/24"),),
        synthetic_token="probe-token",
        max_concurrent_checks=7,
        result_queue_path=str(queue),
    )
    asyncio.run(
        publish_runtime_telemetry(
            config,
            started_at=time.monotonic() - 30,
            transport=httpx.MockTransport(handler),
        )
    )

    assert isinstance(captured["agentVersion"], str)
    assert captured["uptimeSeconds"] >= 29
    assert captured["queueDepth"] == 1
    assert captured["queueCapacity"] == 10000
    assert captured["maxConcurrentChecks"] == 7
