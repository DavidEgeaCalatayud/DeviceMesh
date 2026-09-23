from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_agent_heartbeat_and_device_inventory() -> None:
    payload = {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": "integration-agent",
        "timestamp": "2026-09-23T08:30:00Z",
    }
    assert client.post("/api/v1/agents/heartbeat", json=payload).status_code == 200
    devices = client.get("/api/v1/devices").json()
    assert any(device["id"] == "integration-agent" for device in devices)
