from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)


def test_latest_telemetry_returns_one_sample_per_metric() -> None:
    agent_id = f"latest-{uuid4()}"
    now = datetime.now(UTC)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    telemetry = SqlAlchemyTelemetryRepository(SessionFactory)
    devices.mark_agent_online(agent_id, now, DeviceIdentity(hostname="metric-test"))

    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=now,
            metrics=(Metric("host.memory.utilization.percent", 31.0, "percent"),),
        )
    )
    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=now + timedelta(seconds=5),
            metrics=(Metric("host.memory.utilization.percent", 42.0, "percent"),),
        )
    )

    samples = [sample for sample in telemetry.list_latest() if sample.device_id == agent_id]
    memory = next(
        sample for sample in samples if sample.metric.name == "host.memory.utilization.percent"
    )
    assert memory.metric.value == 42.0
