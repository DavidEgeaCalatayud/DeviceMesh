from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.devices.models import DeviceIdentity
from app.domain.synthetics.models import SyntheticMonitorType, SyntheticState
from app.domain.synthetics.observations import SyntheticProbeObservation
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticMonitorValidationError,
)


def test_synthetic_sla_is_independent_and_tracks_latency_and_outages() -> None:
    device_id = f"synthetic-{uuid4()}"
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    devices.mark_agent_online(device_id, start, DeviceIdentity(hostname="synthetic-test"))

    monitor = repository.create_monitor(
        device_id=device_id,
        name="Public API",
        monitor_type=SyntheticMonitorType.HTTP,
        target="https://example.com/health#ignored",
        interval_seconds=60,
        timeout_seconds=5,
        now=start,
    )
    assert monitor.target == "https://example.com/health"
    assert monitor.expected_status_min == 200
    assert monitor.expected_status_max == 399

    repository.record_batch(
        "probe-eu-1",
        [
            SyntheticProbeObservation(monitor.id, start, True, 20.0, 200),
            SyntheticProbeObservation(monitor.id, start + timedelta(seconds=60), True, 30.0, 200),
            SyntheticProbeObservation(
                monitor.id,
                start + timedelta(seconds=120),
                False,
                50.0,
                503,
                "http_status_503",
            ),
            SyntheticProbeObservation(
                monitor.id,
                start + timedelta(seconds=180),
                False,
                45.0,
                503,
                "http_status_503",
            ),
            SyntheticProbeObservation(monitor.id, start + timedelta(seconds=240), True, 40.0, 200),
        ],
    )

    summary = repository.summarize(monitor.id, start + timedelta(seconds=300))
    day = next(window for window in summary.windows if window.label == "24h")

    assert summary.current_state is SyntheticState.UP
    assert summary.stale is False
    assert day.monitored_seconds == pytest.approx(300.0)
    assert day.up_seconds == pytest.approx(180.0)
    assert day.downtime_seconds == pytest.approx(120.0)
    assert day.availability_percent == pytest.approx(60.0)
    assert day.outage_count == 1
    assert day.longest_outage_seconds == pytest.approx(120.0)
    assert day.latency_average_ms == pytest.approx(30.0)
    assert day.latency_p50_ms == pytest.approx(30.0)
    assert day.latency_p95_ms == pytest.approx(40.0)

    outages = repository.list_outages(
        monitor.id,
        start=start,
        end=start + timedelta(seconds=300),
    )
    assert len(outages) == 1
    assert outages[0].active is False
    assert outages[0].duration_seconds == pytest.approx(120.0)
    assert outages[0].last_failure_reason == "http_status_503"


def test_synthetic_probe_gap_becomes_stale_and_unmonitored() -> None:
    device_id = f"stale-{uuid4()}"
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    devices.mark_agent_online(device_id, start, DeviceIdentity(hostname="stale-test"))
    monitor = repository.create_monitor(
        device_id=device_id,
        name="TCP 443",
        monitor_type=SyntheticMonitorType.TCP,
        target="example.com",
        port=443,
        interval_seconds=60,
        timeout_seconds=5,
        now=start,
    )
    repository.record_batch(
        "probe-eu-1",
        [SyntheticProbeObservation(monitor.id, start, True, 12.0)],
    )

    summary = repository.summarize(monitor.id, start + timedelta(seconds=300))
    day = next(window for window in summary.windows if window.label == "24h")

    assert summary.current_state is SyntheticState.UP
    assert summary.stale is True
    assert day.monitored_seconds == pytest.approx(120.0)
    assert day.up_seconds == pytest.approx(120.0)
    assert day.downtime_seconds == 0.0


def test_synthetic_definition_rejects_unsafe_or_invalid_targets() -> None:
    device_id = f"validation-{uuid4()}"
    now = datetime.now(UTC).replace(microsecond=0)
    repository = SqlAlchemySyntheticRepository(SessionFactory)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    devices.mark_agent_online(device_id, now, DeviceIdentity(hostname="validation-test"))

    with pytest.raises(SyntheticMonitorValidationError):
        repository.create_monitor(
            device_id=device_id,
            name="credentials",
            monitor_type=SyntheticMonitorType.HTTP,
            target="https://user:password@example.com/",
            now=now,
        )

    with pytest.raises(SyntheticMonitorValidationError):
        repository.create_monitor(
            device_id=device_id,
            name="bad tcp",
            monitor_type=SyntheticMonitorType.TCP,
            target="example.com",
            port=None,
            now=now,
        )

    with pytest.raises(SyntheticMonitorValidationError):
        repository.create_monitor(
            device_id=device_id,
            name="bad icmp",
            monitor_type=SyntheticMonitorType.ICMP,
            target="example.com; echo unsafe",
            now=now,
        )
