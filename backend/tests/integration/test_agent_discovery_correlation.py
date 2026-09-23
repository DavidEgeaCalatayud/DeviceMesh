from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.domain.devices.models import DeviceIdentity, DeviceObservation
from app.infrastructure.database import AgentRow, DeviceRow, SessionFactory
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_agent_heartbeat_reuses_device_previously_seen_by_discovery() -> None:
    repository = SqlAlchemyDeviceRepository(SessionFactory)
    now = datetime.now(UTC)
    suffix = ":".join(f"{value:02X}" for value in uuid4().bytes[:4])
    mac = f"02:02:{suffix}"
    hostname = f"correlated-{uuid4()}"
    agent_id = f"agent-{uuid4()}"

    discovered = repository.record_observation(
        DeviceObservation(
            source="integration-probe",
            observed_at=now,
            hostname=hostname,
            ip_address="192.0.2.40",
            mac_address=mac,
        )
    )
    enrolled = repository.mark_agent_online(
        agent_id,
        now + timedelta(seconds=2),
        DeviceIdentity(
            hostname=hostname,
            operating_system="Windows",
            operating_system_version="11",
            ip_addresses=("192.0.2.40",),
            mac_addresses=(mac,),
        ),
    )

    assert enrolled.id == discovered.id
    assert enrolled.operating_system == "Windows"

    with SessionFactory() as session:
        agent = session.get(AgentRow, agent_id)
        assert agent is not None
        assert agent.device_id == discovered.id
        count = session.scalar(
            select(func.count()).select_from(DeviceRow).where(
                DeviceRow.hostname == hostname
            )
        )
        assert count == 1
