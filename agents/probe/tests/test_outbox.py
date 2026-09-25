import asyncio
from pathlib import Path

import httpx
import pytest

from devicemesh_probe.config import ProbeConfig
from devicemesh_probe.outbox import ResultOutbox
from devicemesh_probe.synthetics import DistributedSyntheticClient


def test_outbox_survives_restart_and_applies_backpressure(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    outbox = ResultOutbox(path, capacity=1)
    payload = {"workId": "original", "checkedAt": "2026-09-24T10:00:00Z", "success": False}
    outbox.enqueue(payload)
    with pytest.raises(BufferError):
        outbox.enqueue({"workId": "next"})
    outbox.close()
    reopened = ResultOutbox(path)
    assert reopened.pending() == [("original", payload)]
    reopened.acknowledge("original")
    assert reopened.count() == 0
    reopened.close()


def test_retry_preserves_timestamp_and_work_id(tmp_path: Path) -> None:
    async def scenario() -> None:
        calls = []
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.content)
            return httpx.Response(503 if len(calls) == 1 else 200, json={})
        client = DistributedSyntheticClient(ProbeConfig("https://mesh.example", "test", (),
                   synthetic_token="secret", result_queue_path=str(tmp_path / "queue.sqlite3")),
                   transport=httpx.MockTransport(handler))
        client.outbox.enqueue({"workId": "work", "checkedAt": "2026-09-24T10:00:00Z", "success": True})
        with pytest.raises(httpx.HTTPStatusError):
            await client.flush()
        assert client.outbox.count() == 1
        await client.flush()
        assert calls[0] == calls[1] and client.outbox.count() == 0
        await client.close()
    asyncio.run(scenario())
