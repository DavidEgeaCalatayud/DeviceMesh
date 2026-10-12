from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import security
from app.api.routers.platform import get_platform_repository, get_rca_repository
from app.core.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.repositories.platform import PlatformRepository
from app.infrastructure.repositories.rca import RcaRepository
from app.infrastructure.repositories.synthetics import (
    ServiceIncidentRow,
    SyntheticCheckResultRow,
    SyntheticMonitorRow,
)
from app.infrastructure.security.human_auth import AuditRow, HumanAuthService
from app.main import app


@pytest.fixture
def sre_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(public_reads=False, operator_token="a" * 48)
    auth = HumanAuthService(sessions, settings)
    auth.create_user("operator", "correct horse battery", "operator", "test")
    original = security.get_human_auth_service
    monkeypatch.setattr(security, "get_human_auth_service", lambda: auth)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    app.dependency_overrides[original] = lambda: auth
    app.dependency_overrides[get_platform_repository] = lambda: PlatformRepository(sessions)
    app.dependency_overrides[get_rca_repository] = lambda: RcaRepository(sessions)
    client = TestClient(app)
    token = client.post("/api/v1/auth/login", json={
        "username": "operator", "password": "correct horse battery"
    }).json()["accessToken"]
    try:
        yield client, sessions, {"Authorization": f"Bearer {token}"}
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_service(client: TestClient, headers: dict[str, str], name: str) -> dict[str, object]:
    response = client.post("/api/v1/service-catalog", headers=headers, json={"name": name, "owner": "SRE"})
    assert response.status_code == 201
    return response.json()


def add_monitor(session, monitor_id: str, name: str, now: datetime) -> None:
    session.add(SyntheticMonitorRow(
        id=monitor_id, name=name, kind="http", target="https://example.com",
        interval_seconds=60, timeout_seconds=5, enabled=True, failure_threshold=1,
        recovery_threshold=1, created_by="test", created_at=now, updated_at=now,
        next_run_at=now,
    ))


def add_incident(session, incident_id: str, monitor_id: str, opened_at: datetime) -> None:
    session.add(ServiceIncidentRow(
        id=incident_id, monitor_id=monitor_id, state="open", classification="service_outage",
        opened_at=opened_at, last_observed_at=opened_at, failure_threshold=1,
        recovery_threshold=1, maintenance_active_at_open=False, host_offline_at_open=False,
        failing_probes=1, total_probes=1,
    ))


def test_service_groups_dependency_graph_and_global_mutation_audit(sre_client) -> None:
    client, sessions, headers = sre_client
    api = create_service(client, headers, "API")
    database = create_service(client, headers, "Database")
    storage = create_service(client, headers, "Storage")

    group = client.post("/api/v1/service-groups", headers=headers, json={
        "name": "Checkout", "owner": "SRE", "environment": "production"
    })
    assert group.status_code == 201
    group_id = group.json()["id"]
    assert client.put(
        f"/api/v1/service-groups/{group_id}/services/{api['id']}",
        headers=headers, json={"enabled": True},
    ).status_code == 200

    assert client.put(
        f"/api/v1/service-catalog/{api['id']}/dependencies/{database['id']}",
        headers=headers, json={"kind": "hard"},
    ).status_code == 200
    assert client.put(
        f"/api/v1/service-catalog/{database['id']}/dependencies/{storage['id']}",
        headers=headers, json={"kind": "soft"},
    ).status_code == 200
    cycle = client.put(
        f"/api/v1/service-catalog/{storage['id']}/dependencies/{api['id']}",
        headers=headers, json={"kind": "hard"},
    )
    assert cycle.status_code == 409

    catalog = client.get("/api/v1/service-catalog", headers=headers).json()
    by_id = {item["id"]: item for item in catalog}
    assert by_id[api["id"]]["groupIds"] == [group_id]
    assert by_id[api["id"]]["dependencies"] == [{"serviceId": database["id"], "kind": "hard"}]
    assert by_id[database["id"]]["dependents"] == [{"serviceId": api["id"], "kind": "hard"}]

    assert client.patch(
        f"/api/v1/service-catalog/{api['id']}", headers=headers,
        json={"criticality": "critical", "description": "Public checkout API"},
    ).status_code == 200
    with sessions() as session:
        assert session.scalar(select(AuditRow).where(AuditRow.action == "service.dependency_set"))
        assert session.scalar(select(AuditRow).where(AuditRow.action == "http.mutation"))


def test_incident_correlation_impact_and_postmortem(sre_client) -> None:
    client, sessions, headers = sre_client
    now = datetime.now(UTC)
    api = create_service(client, headers, "API")
    database = create_service(client, headers, "Database")
    monitor_api, monitor_db = str(uuid4()), str(uuid4())
    incident_api, incident_db = str(uuid4()), str(uuid4())
    with sessions.begin() as session:
        add_monitor(session, monitor_api, "API health", now)
        add_monitor(session, monitor_db, "Database health", now)
        session.flush()
        add_incident(session, incident_api, monitor_api, now - timedelta(minutes=4))
        add_incident(session, incident_db, monitor_db, now - timedelta(minutes=3))

    assert client.put(
        f"/api/v1/service-catalog/{api['id']}/monitors/{monitor_api}", headers=headers
    ).status_code == 200
    assert client.put(
        f"/api/v1/service-catalog/{database['id']}/monitors/{monitor_db}", headers=headers
    ).status_code == 200
    assert client.put(
        f"/api/v1/service-catalog/{api['id']}/dependencies/{database['id']}",
        headers=headers, json={"kind": "hard"},
    ).status_code == 200

    detail = client.get(f"/api/v1/incidents/{incident_api}", headers=headers).json()
    assert {item["id"] for item in detail["correlatedIncidents"]} == {incident_db}

    updated = client.patch(
        f"/api/v1/incidents/{incident_api}", headers=headers,
        json={
            "status": "resolved",
            "resolution": "Database capacity restored",
            "impactSummary": "Checkout errors for four minutes",
            "rootCause": "Database connection exhaustion",
            "postmortem": "Add pool saturation alert and capacity test before release.",
        },
    )
    assert updated.status_code == 200
    detail = client.get(f"/api/v1/incidents/{incident_api}", headers=headers).json()
    assert detail["status"] == "resolved"
    assert detail["impactSummary"].startswith("Checkout errors")
    assert detail["postmortem"].startswith("Add pool saturation")
    assert any(item["action"] == "postmortem.updated" for item in detail["timeline"])


def test_explainable_rca_prioritizes_earlier_upstream_failure(sre_client) -> None:
    client, sessions, headers = sre_client
    now = datetime.now(UTC)
    api = create_service(client, headers, "Checkout API")
    database = create_service(client, headers, "Orders Database")
    monitor_api, monitor_db = str(uuid4()), str(uuid4())
    incident_api, incident_db = str(uuid4()), str(uuid4())

    with sessions.begin() as session:
        add_monitor(session, monitor_api, "API health", now)
        add_monitor(session, monitor_db, "Database health", now)
        session.flush()
        add_incident(session, incident_db, monitor_db, now - timedelta(minutes=7))
        add_incident(session, incident_api, monitor_api, now - timedelta(minutes=2))

    assert client.put(
        f"/api/v1/service-catalog/{api['id']}/monitors/{monitor_api}",
        headers=headers,
    ).status_code == 200
    assert client.put(
        f"/api/v1/service-catalog/{database['id']}/monitors/{monitor_db}",
        headers=headers,
    ).status_code == 200
    assert client.put(
        f"/api/v1/service-catalog/{api['id']}/dependencies/{database['id']}",
        headers=headers,
        json={"kind": "hard"},
    ).status_code == 200

    response = client.get(f"/api/v1/incidents/{incident_api}/rca", headers=headers)
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "explained"
    assert report["method"] == "dependency-temporal-evidence-v1"
    assert report["primaryCandidate"]["kind"] == "service"
    assert report["primaryCandidate"]["entityId"] == database["id"]
    assert report["primaryCandidate"]["confidence"] == "high"
    assert report["primaryCandidate"]["causalPath"] == ["Orders Database", "Checkout API"]
    evidence_kinds = {item["kind"] for item in report["primaryCandidate"]["evidence"]}
    assert {"dependency_path", "correlated_incident"} <= evidence_kinds


def test_rca_reports_insufficient_data_without_causal_signals(sre_client) -> None:
    client, sessions, headers = sre_client
    now = datetime.now(UTC)
    service = create_service(client, headers, "Isolated API")
    monitor_id, incident_id = str(uuid4()), str(uuid4())

    with sessions.begin() as session:
        add_monitor(session, monitor_id, "Isolated API health", now)
        session.flush()
        add_incident(session, incident_id, monitor_id, now - timedelta(minutes=1))

    assert client.put(
        f"/api/v1/service-catalog/{service['id']}/monitors/{monitor_id}",
        headers=headers,
    ).status_code == 200

    response = client.get(f"/api/v1/incidents/{incident_id}/rca", headers=headers)
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "insufficient_data"
    assert report["primaryCandidate"]["entityId"] == service["id"]
    assert report["primaryCandidate"]["score"] < 40


def test_time_weighted_slo_and_multiwindow_burn_alert(sre_client) -> None:
    client, sessions, headers = sre_client
    now = datetime.now(UTC)
    service = create_service(client, headers, "Search")
    monitor_id = str(uuid4())
    with sessions.begin() as session:
        add_monitor(session, monitor_id, "Search availability", now)
        session.flush()
        for index, (minutes, success) in enumerate(((3, True), (2, False), (1, False)), start=1):
            session.add(SyntheticCheckResultRow(
                id=index, monitor_id=monitor_id, checked_at=now - timedelta(minutes=minutes),
                success=success, latency_ms=12, probe_id="test",
            ))

    path = f"/api/v1/service-catalog/{service['id']}"
    assert client.put(f"{path}/monitors/{monitor_id}", headers=headers).status_code == 200
    created = client.post(f"{path}/slos", headers=headers, json={
        "name": "Time availability", "monitorId": monitor_id,
        "targetPercent": 99.9, "windowDays": 30, "sliMode": "time",
    })
    assert created.status_code == 201
    report = client.get(f"{path}/slos", headers=headers).json()[0]
    assert report["sli"] == "time_availability"
    assert report["budgetUnit"] == "seconds"
    assert report["observedSeconds"] > 0
    assert report["failedSeconds"] > 0
    assert 0 < report["coveragePercent"] < 1
    assert report["burnRates"]["1h"] > 14.4
    assert report["burnRates"]["6h"] > 6
    assert report["burnAlert"] == "critical"
