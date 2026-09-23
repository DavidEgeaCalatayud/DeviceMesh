from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import MetricSampleRow, SessionFactory
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)


def test_device_and_telemetry_survive_repository_recreation() -> None:
    agent_id = f"integration-{uuid4()}"
    now = datetime.now(UTC)
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    telemetry = SqlAlchemyTelemetryRepository(SessionFactory)

    devices.mark_agent_online(
        agent_id,
        now,
        DeviceIdentity(
            hostname="PC-TEST",
            operating_system="Windows",
            operating_system_version="11",
            architecture="x64",
            ip_addresses=("192.0.2.10",),
            mac_addresses=("AA-BB-CC-DD-EE-FF",),
        ),
    )
    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=now,
            metrics=(Metric("host.cpu.utilization.percent", 17.5, "percent"),),
        )
    )

    recreated = SqlAlchemyDeviceRepository(SessionFactory)
    device = next(item for item in recreated.list_devices() if item.id == agent_id)
    assert device.hostname == "PC-TEST"
    assert device.operating_system == "Windows"
    assert device.ip_addresses == {"192.0.2.10"}
    assert device.mac_addresses == {"AA:BB:CC:DD:EE:FF"}

    with SessionFactory() as session:
        samples = session.scalar(
            select(func.count()).select_from(MetricSampleRow).where(
                MetricSampleRow.device_id == agent_id
            )
        )
        assert samples == 1
