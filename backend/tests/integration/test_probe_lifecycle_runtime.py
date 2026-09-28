from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.domain.synthetics.models import SyntheticMonitorKind
from app.infrastructure.database import SessionFactory
from app.infrastructure.probe_runtime import (
    ProbeCredentialLifecycleRow,
    credential_expired,
)
from app.infrastructure.repositories.synthetics import SqlAlchemySyntheticRepository
from app.infrastructure.security.probe_credentials import ProbeCredentialService
from app.main import app

client = TestClient(app)
OPERATOR_HEADERS = {"Authorization": "Bearer development-operator-change-me"}


def test_probe_credential_expiry_rotation_and_runtime_telemetry() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    registration = repository.create_probe(
        name=f"runtime-{uuid4()}",
        location="Murcia",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now,
    )
    probe_id = registration.probe.id

    assert credential_expired(registration.token, now=now) is False

    with SessionFactory.begin() as session:
        session.execute(
            update(ProbeCredentialLifecycleRow)
            .where(ProbeCredentialLifecycleRow.probe_id == probe_id)
            .values(expires_at=now - timedelta(seconds=1))
        )

    expired = client.post(
        "/api/v1/probes/runtime-heartbeat",
        headers={"Authorization": f"Bearer {registration.token}"},
        json={
            "agentVersion": "0.2.0",
            "uptimeSeconds": 120,
            "queueDepth": 3,
            "queueCapacity": 10000,
            "maxConcurrentChecks": 4,
        },
    )
    assert expired.status_code == 401
    assert "expired" in expired.json()["detail"]

    rotated = ProbeCredentialService(SessionFactory).rotate(probe_id, now=now + timedelta(seconds=2))
    assert credential_expired(rotated.token, now=now + timedelta(seconds=2)) is False

    runtime = client.post(
        "/api/v1/probes/runtime-heartbeat",
        headers={"Authorization": f"Bearer {rotated.token}"},
        json={
            "agentVersion": "0.2.0",
            "uptimeSeconds": 123,
            "queueDepth": 3,
            "queueCapacity": 10000,
            "maxConcurrentChecks": 4,
        },
    )
    assert runtime.status_code == 200
    payload = runtime.json()
    assert payload["probeId"] == probe_id
    assert payload["agentVersion"] == "0.2.0"
    assert payload["uptimeSeconds"] == 123
    assert payload["queueDepth"] == 3
    assert payload["queueCapacity"] == 10000
    assert payload["maxConcurrentChecks"] == 4
    assert payload["credentialExpiresAt"] > payload["credentialRotatedAt"]

    operator = client.get(
        f"/api/v1/operator/synthetic-probes/{probe_id}/runtime",
        headers=OPERATOR_HEADERS,
    )
    assert operator.status_code == 200
    assert operator.json()["queueDepth"] == 3


def test_probe_runtime_rejects_impossible_queue_state() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    registration = repository.create_probe(
        name=f"queue-{uuid4()}",
        location="Madrid",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=datetime.now(UTC),
    )
    response = client.post(
        "/api/v1/probes/runtime-heartbeat",
        headers={"Authorization": f"Bearer {registration.token}"},
        json={
            "agentVersion": "0.2.0",
            "uptimeSeconds": 1,
            "queueDepth": 11,
            "queueCapacity": 10,
            "maxConcurrentChecks": 4,
        },
    )
    assert response.status_code == 422
