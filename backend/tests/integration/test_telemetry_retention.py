from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import DeviceEventRow, MetricSampleRow, SessionFactory
from app.infrastructure.repositories.retention import (
    MetricHourlyRollupRow,
    SqlAlchemyTelemetryRetentionRepository,
)
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)
from app.infrastructure.repositories.synthetics import SyntheticCheckResultRow, SyntheticMonitorRow


def test_compaction_preserves_hourly_statistics_and_merges_late_samples() -> None:
    agent_id = f"retention-{uuid4()}"
    now = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
    sample_hour = now - timedelta(days=2)
    cutoff = now - timedelta(days=1)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    telemetry = SqlAlchemyTelemetryRepository(SessionFactory)
    retention = SqlAlchemyTelemetryRetentionRepository(SessionFactory)
    devices.mark_agent_online(agent_id, sample_hour, DeviceIdentity(hostname="retention-test"))

    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour,
            metrics=(Metric("network.latency.ms", 10.0, "ms"),),
        )
    )
    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour + timedelta(minutes=10),
            metrics=(Metric("network.latency.ms", 20.0, "ms"),),
        )
    )

    first = retention.compact_before(cutoff)
    assert first.raw_samples_deleted >= 2
    raw = telemetry.list_history(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    assert raw.points == ()

    hourly = retention.list_hourly(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    assert len(hourly.points) == 1
    point = hourly.points[0]
    assert point.average == 15.0
    assert point.minimum == 10.0
    assert point.maximum == 20.0
    assert point.samples == 2
    assert point.unit == "ms"

    second = retention.compact_before(cutoff)
    assert second.raw_samples_deleted == 0

    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour + timedelta(minutes=20),
            metrics=(Metric("network.latency.ms", 30.0, "ms"),),
        )
    )
    third = retention.compact_before(cutoff)
    assert third.raw_samples_deleted == 1

    merged = retention.list_hourly(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    merged_point = merged.points[0]
    assert merged_point.average == 20.0
    assert merged_point.minimum == 10.0
    assert merged_point.maximum == 30.0
    assert merged_point.samples == 3


def test_policy_compacts_raw_and_expires_archived_operational_data() -> None:
    agent_id = f"retention-policy-{uuid4()}"
    monitor_id = str(uuid4())
    now = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
    very_old = now - timedelta(days=400)
    recent_raw = now - timedelta(days=10)
    expired_operational = now - timedelta(days=100)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    devices.mark_agent_online(agent_id, now, DeviceIdentity(hostname="retention-policy-test"))
    with SessionFactory.begin() as session:
        session.add_all([
            MetricSampleRow(device_id=agent_id, metric_type="cpu.usage", timestamp=very_old,
                            value=12.0, unit="percent"),
            MetricSampleRow(device_id=agent_id, metric_type="cpu.usage", timestamp=recent_raw,
                            value=42.0, unit="percent"),
            DeviceEventRow(device_id=agent_id, name="test.expired", severity="info",
                           timestamp=expired_operational, attributes={}),
            SyntheticMonitorRow(id=monitor_id, name="retention", kind="http",
                                target="https://example.com", port=None, device_id=agent_id,
                                interval_seconds=60, timeout_seconds=5, enabled=True,
                                http_method="GET", expected_status=200, failure_threshold=3,
                                recovery_threshold=2, created_by="test", created_at=now,
                                updated_at=now, next_run_at=now),
        ])
        session.flush()
        session.add(SyntheticCheckResultRow(
            monitor_id=monitor_id, checked_at=expired_operational, success=True,
            latency_ms=10, http_status=200, error_kind=None, error=None,
            probe_id="test", probe_location=None, work_id=None,
        ))

    retention = SqlAlchemyTelemetryRetentionRepository(SessionFactory)
    result = retention.enforce_policy(
        now,
        raw_retention_days=7,
        hourly_retention_days=365,
        event_retention_days=90,
        synthetic_check_retention_days=90,
    )

    assert result.raw_samples_deleted >= 2
    assert result.hourly_rollups_deleted >= 1
    assert result.events_deleted >= 1
    assert result.synthetic_checks_deleted >= 1
    with SessionFactory() as session:
        assert session.scalar(select(MetricSampleRow.id).where(MetricSampleRow.device_id == agent_id)) is None
        hourly = list(session.scalars(select(MetricHourlyRollupRow).where(
            MetricHourlyRollupRow.device_id == agent_id
        )))
        assert len(hourly) == 1
        assert hourly[0].bucket_start.date() == recent_raw.date()
        assert session.scalar(select(DeviceEventRow.id).where(
            DeviceEventRow.device_id == agent_id,
            DeviceEventRow.name == "test.expired",
        )) is None
        assert session.scalar(select(SyntheticCheckResultRow.id).where(
            SyntheticCheckResultRow.monitor_id == monitor_id
        )) is None
