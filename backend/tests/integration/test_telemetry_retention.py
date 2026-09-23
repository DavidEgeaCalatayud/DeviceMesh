from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.retention import SqlAlchemyTelemetryRetentionRepository
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)


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
