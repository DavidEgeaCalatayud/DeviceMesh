from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import security
from app.api.routers.platform import get_platform_repository
from app.core.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.repositories.platform import PlatformRepository
from app.infrastructure.repositories.synthetics import (
    ServiceIncidentRow,
    SyntheticCheckResultRow,
    SyntheticMonitorRow,
)
from app.infrastructure.security.human_auth import AuditRow, HumanAuthService, HumanSessionRow
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
    app.dependency_overrides[get_platform_repository] = lambda: PlatformRepository(sessions)
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


def test_rbac_revocation_refresh_and_no_password_disclosure(secured) -> None:
    client, auth, sessions = secured
    auth.create_user("viewer", "correct horse battery", "viewer", "test")
    auth.create_user("operator", "correct horse battery", "operator", "test")
    viewer = login(client, "viewer")
    headers = {"Authorization": f"Bearer {viewer['accessToken']}"}
    assert client.get("/api/v1/service-catalog").status_code == 401
    assert client.get("/api/v1/service-catalog", headers=headers).status_code == 200
    assert client.post("/api/v1/service-catalog", headers=headers, json={"name": "API"}).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    operator = login(client, "operator")
    operator_headers = {"Authorization": f"Bearer {operator['accessToken']}"}
    assert client.post("/api/v1/operator/agent-enrollment-tokens", headers=operator_headers, json={}).status_code == 403
    assert client.post("/api/v1/service-catalog", headers=operator_headers, json={"name": "API"}).status_code == 201
    rotated = client.post("/api/v1/auth/refresh", json={"refreshToken": viewer["refreshToken"]})
    assert rotated.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refreshToken": viewer["refreshToken"]}).status_code == 401
    new_headers = {"Authorization": f"Bearer {rotated.json()['accessToken']}"}
    assert client.post("/api/v1/auth/logout", headers=new_headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 401
    with sessions() as session:
        tokens = list(session.scalars(select(HumanSessionRow)))
        assert all(row.token_digest != viewer["accessToken"] for row in tokens)
        assert session.scalar(select(AuditRow).where(AuditRow.action == "user.logout"))


def test_login_throttling_and_disabled_user(secured) -> None:
    client, auth, _ = secured
    auth.create_user("viewer", "correct horse battery", "viewer", "test")
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"username": "viewer", "password": "bad"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "viewer", "password": "bad"}).status_code == 429


def test_incident_workflow_audit_and_slo_unknown(secured) -> None:
    client, auth, sessions = secured
    auth.create_user("operator", "correct horse battery", "operator", "test")
    headers = {"Authorization": f"Bearer {login(client, 'operator')['accessToken']}"}
    now = datetime.now(UTC)
    monitor_id, incident_id = str(uuid4()), str(uuid4())
    with sessions.begin() as session:
        session.add(SyntheticMonitorRow(id=monitor_id, name="API", kind="http", target="https://example.com",
                    interval_seconds=60, timeout_seconds=5, enabled=True, failure_threshold=1,
                    recovery_threshold=1, created_by="test", created_at=now, updated_at=now, next_run_at=now))
        session.flush()
        session.add(ServiceIncidentRow(id=incident_id, monitor_id=monitor_id, state="open",
                    classification="service_outage", opened_at=now, last_observed_at=now,
                    failure_threshold=1, recovery_threshold=1, maintenance_active_at_open=False,
                    host_offline_at_open=False, failing_probes=1, total_probes=1))
    service = client.post("/api/v1/service-catalog", headers=headers, json={"name": "Payments", "owner": "SRE"}).json()
    path = f"/api/v1/service-catalog/{service['id']}"
    assert client.put(f"{path}/monitors/{monitor_id}", headers=headers).status_code == 200
    assert client.post(f"{path}/slos", headers=headers, json={"name": "Availability", "monitorId": monitor_id,
                       "targetPercent": 99.9, "windowDays": 30}).status_code == 201
    report = client.get(f"{path}/slos", headers=headers).json()[0]
    assert report["status"] == "unknown" and report["actualPercent"] is None
    with sessions.begin() as session:
        session.add(SyntheticCheckResultRow(id=1, monitor_id=monitor_id, checked_at=now - timedelta(minutes=1),
                    success=False, latency_ms=10, probe_id="test"))
    report = client.get(f"{path}/slos", headers=headers).json()[0]
    assert report["status"] == "breached" and report["burnRates"]["1h"] == pytest.approx(1000)
    incident_path = f"/api/v1/incidents/{incident_id}"
    assert client.patch(incident_path, headers=headers, json={"status": "mitigated"}).status_code == 409
    assert client.patch(incident_path, headers=headers, json={"status": "acknowledged", "assignedTo": "on-call"}).status_code == 200
    assert client.patch(incident_path, headers=headers, json={"status": "resolved"}).status_code == 409
    assert client.patch(incident_path, headers=headers, json={"note": "Database restarted"}).status_code == 200
    assert client.patch(incident_path, headers=headers, json={"status": "resolved", "resolution": "Recovered"}).status_code == 200
    assert client.patch(incident_path, headers=headers, json={"status": "open"}).status_code == 200
    detail = client.get(incident_path, headers=headers).json()
    assert detail["serviceIds"] == [service["id"]]
    assert detail["status"] == "open" and detail["resolvedAt"] is None
    assert len(detail["timeline"]) == 4
