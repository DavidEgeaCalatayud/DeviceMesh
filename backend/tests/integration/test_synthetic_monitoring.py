from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.synthetics.models import SyntheticCheckErrorKind, SyntheticMonitorKind
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.synthetics import SqlAlchemySyntheticRepository


def test_synthetic_monitor_persists_results_and_calculates_separate_sla() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    monitor = repository.create_monitor(
        name=f"api-{uuid4()}",
        kind=SyntheticMonitorKind.HTTP,
        target="https://example.com/health",
        port=None,
        device_id=None,
        interval_seconds=60,
        timeout_seconds=5,
        http_method="GET",
        expected_status=200,
        now=now - timedelta(hours=3),
    )

    repository.record_result(
        monitor_id=monitor.id,
        success=True,
        latency_ms=120.0,
        http_status=200,
        error_kind=None,
        error=None,
        probe_id="test-probe",
        checked_at=now - timedelta(hours=2),
    )
    repository.record_result(
        monitor_id=monitor.id,
        success=False,
        latency_ms=5000.0,
        http_status=None,
        error_kind=SyntheticCheckErrorKind.TIMEOUT,
        error="probe timed out",
        probe_id="test-probe",
        checked_at=now - timedelta(hours=1),
    )
    repository.record_result(
        monitor_id=monitor.id,
        success=True,
        latency_ms=80.0,
        http_status=200,
        error_kind=None,
        error=None,
        probe_id="test-probe",
        checked_at=now,
    )

    summary = repository.summarize(monitor.id, now)
    day = next(window for window in summary.windows if window.label == "24h")
    assert day.total_checks == 3
    assert day.successful_checks == 2
    assert day.failed_checks == 1
    assert day.availability_percent == pytest.approx(66.666666, rel=1e-5)
    assert day.mean_latency_ms == pytest.approx(100.0)
    assert day.p95_latency_ms == pytest.approx(120.0)
    assert summary.consecutive_failures == 0
    assert summary.failing_since is None


def test_disabled_synthetic_monitor_is_not_claimed() -> None:
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    now = datetime.now(UTC).replace(microsecond=0)
    monitor = repository.create_monitor(
        name=f"disabled-{uuid4()}",
        kind=SyntheticMonitorKind.TCP,
        target="example.com",
        port=443,
        device_id=None,
        interval_seconds=60,
        timeout_seconds=5,
        http_method=None,
        expected_status=None,
        now=now,
    )
    repository.set_enabled(monitor.id, False, now=now)
    claimed = repository.claim_due(now=now + timedelta(minutes=5), limit=100)
    assert all(item.id != monitor.id for item in claimed)
