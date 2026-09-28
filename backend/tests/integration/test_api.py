from datetime import UTC, datetime
from uuid import uuid4

import pytest
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
    assert payload["schemaRevision"] == "0017"
    assert payload["componentCompatibility"] == {
        "windows-agent": {"minimumVersion": "0.2.0", "protocolVersions": [1]},
        "linux-agent": {"minimumVersion": "0.2.0", "protocolVersions": [1]},
        "macos-agent": {"minimumVersion": "0.1.0", "protocolVersions": [1]},
        "distributed-probe": {"minimumVersion": "0.2.0", "protocolVersions": [1]},
    }


@pytest.mark.parametrize(
    ("component", "package_version"),
    [
        ("windows-agent", "0.2.0"),
        ("linux-agent", "0.2.0"),
        ("macos-agent", "0.1.0"),
        ("distributed-probe", "0.2.0"),
    ],
)
def test_component_compatibility_accepts_supported_clients(
    component: str,
    package_version: str,
) -> None:
    response = client.get(
        f"/api/v1/system/compatibility/{component}",
        params={"packageVersion": package_version, "protocolVersion": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["compatible"] is True
    assert payload["reason"] == "compatible"
    assert payload["minimumVersion"] == package_version
    assert payload["supportedProtocolVersions"] == [1]


def test_component_compatibility_rejects_old_or_wrong_protocol_clients() -> None:
    old = client.get(
        "/api/v1/system/compatibility/windows-agent",
        params={"packageVersion": "0.1.99", "protocolVersion": 1},
    )
    assert old.status_code == 200
    assert old.json()["compatible"] is False
    assert old.json()["reason"] == "package_too_old"

    wrong_protocol = client.get(
        "/api/v1/system/compatibility/linux-agent",
        params={"packageVersion": "99.0.0", "protocolVersion": 2},
    )
    assert wrong_protocol.status_code == 200
    assert wrong_protocol.json()["compatible"] is False
    assert wrong_protocol.json()["reason"] == "unsupported_protocol"

    invalid_version = client.get(
        "/api/v1/system/compatibility/distributed-probe",
        params={"packageVersion": "next.release", "protocolVersion": 1},
    )
    assert invalid_version.status_code == 200
    assert invalid_version.json()["compatible"] is False
    assert invalid_version.json()["reason"] == "invalid_version"

    unknown = client.get(
        "/api/v1/system/compatibility/unknown-agent",
        params={"packageVersion": "1.0.0", "protocolVersion": 1},
    )
    assert unknown.status_code == 404


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
