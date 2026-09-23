from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)


def test_history_returns_deterministic_raw_and_bucketed_series() -> None:
    agent_id = f"history-{uuid4()}"
    start = datetime.now(UTC).replace(second=0, microsecond=0)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    telemetry = SqlAlchemyTelemetryRepository(SessionFactory)
    devices.mark_agent_online(agent_id, start, DeviceIdentity(hostname="history-test"))

    for offset, value in ((0, 10.0), (30, 20.0), (60, 30.0), (90, 50.0)):
        telemetry.append(
            TelemetryBatch(
                agent_id=agent_id,
                timestamp=start + timedelta(seconds=offset),
                metrics=(Metric("network.latency.ms", value, "ms"),),
            )
        )

    raw = telemetry.list_history(
        agent_id,
        "network.latency.ms",
        start,
        start + timedelta(minutes=2),
    )
    assert [point.value for point in raw.points] == [10.0, 20.0, 30.0, 50.0]

    bucketed = telemetry.list_history(
        agent_id,
        "network.latency.ms",
        start,
        start + timedelta(minutes=2),
        bucket_seconds=60,
    )
    assert len(bucketed.points) == 2
    assert bucketed.points[0].value == pytest.approx(15.0)
    assert bucketed.points[0].minimum == 10.0
    assert bucketed.points[0].maximum == 20.0
    assert bucketed.points[0].samples == 2
    assert bucketed.points[1].value == pytest.approx(40.0)
