from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.synthetics.models import (
    ServiceConsensusClassification,
    ServiceIncidentState,
    SyntheticCheckErrorKind,
    SyntheticMonitorKind,
)
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.synthetic_consensus import RoundAwareSyntheticRepository


def _setup_monitor(repository: RoundAwareSyntheticRepository, now: datetime) -> tuple[str, str, str]:
    monitor = repository.create_monitor(
        name=f"consensus-v2-{uuid4()}",
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
    )
    probe_ids: list[str] = []
    for location in ("Murcia", "Madrid"):
        probe = repository.create_probe(
            name=f"{location.lower()}-{uuid4()}",
            location=location,
            capabilities=(SyntheticMonitorKind.HTTP,),
            now=now,
        ).probe
        repository.heartbeat_probe(probe.id, now=now)
        repository.assign_probe(monitor.id, probe.id, now=now)
        probe_ids.append(probe.id)
    return monitor.id, probe_ids[0], probe_ids[1]


def _record(
    repository: RoundAwareSyntheticRepository,
    monitor_id: str,
    probe_id: str,
    checked_at: datetime,
    *,
    success: bool,
) -> None:
    repository.record_result(
        monitor_id=monitor_id,
        success=success,
        latency_ms=80 if success else 5000,
        http_status=200 if success else None,
        error_kind=None if success else SyntheticCheckErrorKind.TIMEOUT,
        error=None if success else "probe timed out",
        probe_id=probe_id,
        probe_location=probe_id,
        checked_at=checked_at,
    )


def test_consensus_waits_for_round_quorum_before_classifying() -> None:
    repository = RoundAwareSyntheticRepository(
        SessionFactory,
        quorum_ratio=0.5,
        minimum_quorum=1,
        round_window_seconds=30,
        probe_stale_seconds=120,
    )
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id, murcia, madrid = _setup_monitor(repository, now)

    _record(repository, monitor_id, murcia, now + timedelta(seconds=1), success=False)
    partial = repository.consensus(monitor_id, now + timedelta(seconds=1))
    assert partial.classification is ServiceConsensusClassification.INSUFFICIENT_DATA
    assert len(partial.states) == 1

    _record(repository, monitor_id, madrid, now + timedelta(seconds=2), success=True)
    complete = repository.consensus(monitor_id, now + timedelta(seconds=2))
    assert complete.classification is ServiceConsensusClassification.REGIONAL_DEGRADATION
    assert complete.healthy_probes == 1
    assert complete.failing_probes == 1
    assert repository.incidents(monitor_id, now=now + timedelta(seconds=2)).open_incident is None


def test_previous_round_cannot_satisfy_new_round_quorum() -> None:
    repository = RoundAwareSyntheticRepository(
        SessionFactory,
        quorum_ratio=0.5,
        minimum_quorum=1,
        round_window_seconds=30,
        probe_stale_seconds=180,
    )
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id, murcia, madrid = _setup_monitor(repository, now)

    _record(repository, monitor_id, murcia, now + timedelta(seconds=1), success=False)
    _record(repository, monitor_id, madrid, now + timedelta(seconds=2), success=True)

    second_round = now + timedelta(seconds=61)
    _record(repository, monitor_id, murcia, second_round, success=False)
    partial = repository.consensus(monitor_id, second_round)
    assert partial.classification is ServiceConsensusClassification.INSUFFICIENT_DATA
    assert len(partial.states) == 1
    assert repository.incidents(monitor_id, now=second_round).open_incident is None

    _record(repository, monitor_id, madrid, second_round + timedelta(seconds=1), success=True)
    complete = repository.consensus(monitor_id, second_round + timedelta(seconds=1))
    assert complete.classification is ServiceConsensusClassification.REGIONAL_DEGRADATION

    incident = repository.incidents(monitor_id, now=second_round + timedelta(seconds=1)).open_incident
    assert incident is not None
    assert incident.state is ServiceIncidentState.OPEN


def test_quorum_is_strict_majority_of_active_assigned_probes() -> None:
    repository = RoundAwareSyntheticRepository(
        SessionFactory,
        quorum_ratio=0.5,
        minimum_quorum=1,
        round_window_seconds=30,
        probe_stale_seconds=120,
    )
    now = datetime.now(UTC).replace(microsecond=0)
    monitor_id, first, second = _setup_monitor(repository, now)
    third = repository.create_probe(
        name=f"barcelona-{uuid4()}",
        location="Barcelona",
        capabilities=(SyntheticMonitorKind.HTTP,),
        now=now,
    ).probe
    repository.heartbeat_probe(third.id, now=now)
    repository.assign_probe(monitor_id, third.id, now=now)

    _record(repository, monitor_id, first, now + timedelta(seconds=1), success=True)
    one = repository.consensus(monitor_id, now + timedelta(seconds=1))
    assert one.classification is ServiceConsensusClassification.INSUFFICIENT_DATA

    _record(repository, monitor_id, second, now + timedelta(seconds=2), success=True)
    two = repository.consensus(monitor_id, now + timedelta(seconds=2))
    assert two.classification is ServiceConsensusClassification.HEALTHY
    assert len(two.states) == 2
