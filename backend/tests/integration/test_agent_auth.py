from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.security.agent_auth import AgentAuthService, EnrollmentTokenInvalidError
from app.main import app

client = TestClient(app)
OPERATOR_HEADERS = {"Authorization": "Bearer development-operator-change-me"}


def _issue_and_enroll(agent_id: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/operator/agent-enrollment-tokens",
        json={},
        headers=OPERATOR_HEADERS,
    )
    assert token.status_code == 200
    enrolled = client.post(
        "/api/v1/agents/enroll",
        json={"token": token.json()["token"], "agentId": agent_id},
    )
    assert enrolled.status_code == 200
    return {str(key): str(value) for key, value in enrolled.json().items()}


def _headers(agent_id: str, credential: str, nonce: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Agent {credential}",
        "X-DeviceMesh-Agent-ID": agent_id,
        "X-DeviceMesh-Timestamp": datetime.now(UTC).isoformat(),
        "X-DeviceMesh-Nonce": nonce or uuid4().hex,
    }


def _heartbeat(agent_id: str) -> dict[str, object]:
    return {
        "type": "heartbeat",
        "protocolVersion": 1,
        "agentId": agent_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def test_enrollment_token_is_one_time() -> None:
    token_response = client.post(
        "/api/v1/operator/agent-enrollment-tokens",
        json={},
        headers=OPERATOR_HEADERS,
    )
    token = token_response.json()["token"]
    assert client.post("/api/v1/agents/enroll", json={"token": token, "agentId": "one-time-a"}).status_code == 200
    assert client.post("/api/v1/agents/enroll", json={"token": token, "agentId": "one-time-b"}).status_code == 409


def test_expired_enrollment_token_is_rejected() -> None:
    service = AgentAuthService(SessionFactory, get_settings())
    past = datetime.now(UTC) - timedelta(hours=1)
    token = service.create_enrollment_token(ttl_seconds=60, now=past)
    try:
        service.enroll(token.token, "expired-agent")
    except EnrollmentTokenInvalidError:
        pass
    else:
        raise AssertionError("expired enrollment token was accepted")


def test_human_token_cannot_authenticate_agent_ingestion() -> None:
    response = client.post(
        "/api/v1/agents/heartbeat",
        json=_heartbeat("human-token-agent"),
        headers=OPERATOR_HEADERS,
    )
    assert response.status_code == 401


def test_replayed_agent_request_is_rejected() -> None:
    agent_id = f"replay-{uuid4().hex[:8]}"
    enrolled = _issue_and_enroll(agent_id)
    headers = _headers(agent_id, enrolled["credential"], "same-nonce")
    payload = _heartbeat(agent_id)
    assert client.post("/api/v1/agents/heartbeat", json=payload, headers=headers).status_code == 200
    assert client.post("/api/v1/agents/heartbeat", json=payload, headers=headers).status_code == 409


def test_revoked_agent_credential_stops_ingestion() -> None:
    agent_id = f"revoked-{uuid4().hex[:8]}"
    enrolled = _issue_and_enroll(agent_id)
    revoke = client.delete(
        f"/api/v1/operator/agents/{agent_id}/credentials/{enrolled['credentialId']}",
        headers=OPERATOR_HEADERS,
    )
    assert revoke.status_code == 204
    response = client.post(
        "/api/v1/agents/heartbeat",
        json=_heartbeat(agent_id),
        headers=_headers(agent_id, enrolled["credential"]),
    )
    assert response.status_code == 401


def test_rotation_revokes_previous_credential() -> None:
    agent_id = f"rotate-{uuid4().hex[:8]}"
    enrolled = _issue_and_enroll(agent_id)
    rotated = client.post(
        f"/api/v1/operator/agents/{agent_id}/credentials/rotate",
        headers=OPERATOR_HEADERS,
    )
    assert rotated.status_code == 200
    old_response = client.post(
        "/api/v1/agents/heartbeat",
        json=_heartbeat(agent_id),
        headers=_headers(agent_id, enrolled["credential"]),
    )
    assert old_response.status_code == 401
    new_credential = str(rotated.json()["credential"])
    new_response = client.post(
        "/api/v1/agents/heartbeat",
        json=_heartbeat(agent_id),
        headers=_headers(agent_id, new_credential),
    )
    assert new_response.status_code == 200
