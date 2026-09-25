from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OPERATOR_HEADERS = {"Authorization": "Bearer development-operator-change-me"}


def _enroll(agent_id: str) -> str:
    token_response = client.post(
        "/api/v1/operator/agent-enrollment-tokens",
        json={},
        headers=OPERATOR_HEADERS,
    )
    assert token_response.status_code == 200
    enrollment = client.post(
        "/api/v1/agents/enroll",
        json={"token": token_response.json()["token"], "agentId": agent_id},
    )
    assert enrollment.status_code == 200
    return str(enrollment.json()["credential"])


def _agent_headers(agent_id: str, credential: str) -> dict[str, str]:
    return {
        "Authorization": f"Agent {credential}",
        "X-DeviceMesh-Agent-ID": agent_id,
        "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
        "X-DeviceMesh-Nonce": uuid4().hex,
    }


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_system_version_publishes_compatibility_contract() -> None:
    response = client.get("/api/v1/system/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["apiVersion"] == 1
    assert payload["protocolVersion"] == 1
    assert payload["supportedProtocolVersions"] == [1]
    assert payload["minProtocolVersion"] == 1
    assert payload["maxProtocolVersion"] == 1
    assert payload["schemaRevision"] == "0014"
    assert payload["componentCompatibility"] == {
        "windows-agent": {"protocolVersions": [1]},
        "linux-agent": {"protocolVersions": [1]},
        "macos-agent": {"protocolVersions": [1]},
        "distributed-probe": {"protocolVersions": [1]},
    }


def test_agent_heartbeat_and_device_inventory() -> None:
    agent_id = f"integration-agent-{uuid4().hex[:8]}"
    credential = _enroll(agent_id)
    payload = {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    response = client.post(
        "/api/v1/agents/heartbeat",
        json=payload,
        headers=_agent_headers(agent_id, credential),
    )
    assert response.status_code == 200
    devices = client.get("/api/v1/devices").json()
    assert any(device["id"] == agent_id for device in devices)
