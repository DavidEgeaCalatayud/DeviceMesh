from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceObservation
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.event_recording import EventRecordingDeviceRepository
from app.infrastructure.repositories.events import SqlAlchemyEventRepository
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_discovery_and_ip_change_append_timeline_events() -> None:
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    events = SqlAlchemyEventRepository(SessionFactory)
    repository = EventRecordingDeviceRepository(devices, events)
    now = datetime.now(UTC)
    suffix = ":".join(f"{value:02X}" for value in uuid4().bytes[:4])
    mac = f"02:01:{suffix}"

    first = repository.record_observation(
        DeviceObservation(
            source="integration-probe",
            observed_at=now,
            hostname=f"timeline-{uuid4()}",
            ip_address="192.0.2.30",
            mac_address=mac,
        )
    )
    repository.record_observation(
        DeviceObservation(
            source="integration-probe",
            observed_at=now + timedelta(seconds=5),
            hostname=first.hostname,
            ip_address="192.0.2.31",
            mac_address=mac,
        )
    )

    names = [event.name for event in events.list_recent(50) if event.device_id == first.id]
    assert "DEVICE_DISCOVERED" in names
    assert "IP_CHANGED" in names
