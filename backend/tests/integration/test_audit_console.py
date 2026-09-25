from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import security
from app.core.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.security.human_auth import HumanAuthService, audit
from app.main import app


@pytest.fixture
def secured(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(public_reads=False, operator_token="a" * 48)
    auth = HumanAuthService(sessions, settings)
    original = security.get_human_auth_service
    monkeypatch.setattr(security, "get_human_auth_service", lambda: auth)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    app.dependency_overrides[original] = lambda: auth
    client = TestClient(app)
    try:
        yield client, auth, sessions
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "correct horse battery"})
    assert response.status_code == 200
    return response.json()


def test_audit_log_is_admin_only_filterable_and_exportable(secured) -> None:
    client, auth, sessions = secured
    auth.create_user("admin", "correct horse battery", "administrator", "test")
    auth.create_user("viewer", "correct horse battery", "viewer", "test")
    admin_headers = {"Authorization": f"Bearer {login(client, 'admin')['accessToken']}"}
    viewer_headers = {"Authorization": f"Bearer {login(client, 'viewer')['accessToken']}"}

    now = datetime.now(UTC)
    with sessions.begin() as session:
        audit(session, "admin-user", "incident.updated", "incident-123",
              {"status": "resolved"}, source_ip="10.0.0.5", request_id="req-1")
        audit(session, "probe-7", "probe.rotated", "probe-7",
              {"reason": "scheduled"}, source_ip="10.0.0.7", request_id="req-2")

    assert client.get("/api/v1/admin/audit-log", headers=viewer_headers).status_code == 403

    filtered = client.get(
        "/api/v1/admin/audit-log",
        headers=admin_headers,
        params={"action": "incident.updated", "resource": "incident", "sourceIp": "10.0.0.5"},
    )
    assert filtered.status_code == 200
    rows = filtered.json()
    assert len(rows) == 1
    assert rows[0]["actor"] == "admin-user"
    assert rows[0]["requestId"] == "req-1"
    assert rows[0]["metadata"] == {"status": "resolved"}

    searched = client.get("/api/v1/admin/audit-log", headers=admin_headers, params={"search": "probe-7"})
    assert searched.status_code == 200
    assert any(row["action"] == "probe.rotated" for row in searched.json())

    windowed = client.get(
        "/api/v1/admin/audit-log",
        headers=admin_headers,
        params={"since": (now - timedelta(minutes=1)).isoformat(), "until": (now + timedelta(minutes=1)).isoformat()},
    )
    assert windowed.status_code == 200
    assert len(windowed.json()) >= 2

    invalid = client.get(
        "/api/v1/admin/audit-log",
        headers=admin_headers,
        params={"since": (now + timedelta(minutes=1)).isoformat(), "until": now.isoformat()},
    )
    assert invalid.status_code == 422

    exported = client.get(
        "/api/v1/admin/audit-log.csv",
        headers=admin_headers,
        params={"requestId": "req-1"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"devicemesh-audit-log.csv\"" == exported.headers["content-disposition"]
    assert "incident.updated" in exported.text
    assert "probe.rotated" not in exported.text
