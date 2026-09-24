from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.synthetics.models import (
    ServiceConsensusClassification,
    ServiceIncidentClassification,
    ServiceIncidentState,
    SyntheticCheckErrorKind,
    SyntheticMonitorKind,
)
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticProbeAuthenticationError,
)


def _monitor(repository: SqlAlchemySyntheticRepository, now: datetime) -> str:
    return repository.create_monitor(
        name=f"distributed-{uuid4()}",
        kind=SyntheticMonitorKind.HTTP,
        target="https://example.com/health",
        port=None,
        device_id=None,
        interval_seconds=60,
        timeout_seconds=5,
        http_method="GET",
        expected_status=200,
        failure_threshold=2,
        recovery_threshold=2,
        now=now,
    ).id


def test_distributed_probe_work_is_authenticated_leased_and_idempotent() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id = _monitor(repository, now)
    registration = repository.create_probe(
        name=f"murcia-{uuid4()}",
        location="Murcia",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now,
    )

    assert repository.authenticate_probe(registration.token).id == registration.probe.id
    with pytest.raises(SyntheticProbeAuthenticationError):
        repository.authenticate_probe("wrong-token")

    repository.heartbeat_probe(registration.probe.id, now=now)
    repository.assign_probe(monitor_id, registration.probe.id, now=now)
    work = repository.claim_probe_work(registration.probe.id, now=now, limit=10)
    assert len(work) == 1
    assert work[0].monitor.id == monitor_id

    first = repository.complete_probe_work(
        work_id=work[0].id,
        probe_id=registration.probe.id,
        success=True,
        latency_ms=42.0,
        http_status=200,
        error_kind=None,
        error=None,
        checked_at=now + timedelta(seconds=1),
    )
    retried = repository.complete_probe_work(
        work_id=work[0].id,
        probe_id=registration.probe.id,
        success=True,
        latency_ms=42.0,
        http_status=200,
        error_kind=None,
        error=None,
        checked_at=now + timedelta(seconds=2),
    )
    assert retried.id == first.id
    assert first.work_id == work[0].id
    assert first.probe_location == "Murcia"


def test_multi_probe_consensus_opens_and_recovers_service_incident() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id = _monitor(repository, now)
    murcia = repository.create_probe(
        name=f"murcia-{uuid4()}",
        location="Murcia",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now,
    ).probe
    madrid = repository.create_probe(
        name=f"madrid-{uuid4()}",
        location="Madrid",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now,
    ).probe
    for probe in (murcia, madrid):
        repository.heartbeat_probe(probe.id, now=now)
        repository.assign_probe(monitor_id, probe.id, now=now)

    murcia_work = repository.claim_probe_work(murcia.id, now=now)[0]
    madrid_work = repository.claim_probe_work(madrid.id, now=now)[0]
    repository.complete_probe_work(
        work_id=murcia_work.id,
        probe_id=murcia.id,
        success=False,
        latency_ms=5000,
        http_status=None,
        error_kind=SyntheticCheckErrorKind.TIMEOUT,
        error="probe timed out",
        checked_at=now + timedelta(seconds=1),
    )
    repository.complete_probe_work(
        work_id=madrid_work.id,
        probe_id=madrid.id,
        success=True,
        latency_ms=80,
        http_status=200,
        error_kind=None,
        error=None,
        checked_at=now + timedelta(seconds=2),
    )

    consensus = repository.consensus(monitor_id, now + timedelta(seconds=2))
    assert consensus.classification is ServiceConsensusClassification.REGIONAL_DEGRADATION
    assert consensus.healthy_probes == 1
    assert consensus.failing_probes == 1

    incident_summary = repository.incidents(monitor_id, now=now + timedelta(seconds=2))
    assert incident_summary.open_incident is not None
    assert incident_summary.open_incident.state is ServiceIncidentState.OPEN
    assert (
        incident_summary.open_incident.classification
        is ServiceIncidentClassification.REGIONAL_PATH
    )

    next_run = now + timedelta(seconds=61)
    murcia_recovery = repository.claim_probe_work(murcia.id, now=next_run)[0]
    madrid_recovery = repository.claim_probe_work(madrid.id, now=next_run)[0]
    for offset, work, probe in (
        (1, murcia_recovery, murcia),
        (2, madrid_recovery, madrid),
    ):
        repository.complete_probe_work(
            work_id=work.id,
            probe_id=probe.id,
            success=True,
            latency_ms=70,
            http_status=200,
            error_kind=None,
            error=None,
            checked_at=next_run + timedelta(seconds=offset),
        )

    recovered = repository.incidents(monitor_id, now=next_run + timedelta(seconds=2))
    assert recovered.open_incident is None
    assert recovered.resolved_count == 1
    assert recovered.mean_recovery_seconds is not None
    assert recovered.mean_recovery_seconds > 0


def test_local_worker_falls_back_when_assigned_probe_is_stale() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id = _monitor(repository, now)
    probe = repository.create_probe(
        name=f"cloud-{uuid4()}",
        location="Cloud",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now - timedelta(minutes=10),
    ).probe
    repository.heartbeat_probe(probe.id, now=now - timedelta(minutes=10))
    repository.assign_probe(monitor_id, probe.id, now=now - timedelta(minutes=10))

    claimed = repository.claim_due(now=now, limit=100, probe_stale_seconds=120)

    assert monitor_id in {item.id for item in claimed}
