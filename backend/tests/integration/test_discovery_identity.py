from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceObservation
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_mac_observations_keep_stable_device_identity_across_ip_change() -> None:
    repository = SqlAlchemyDeviceRepository(SessionFactory)
    now = datetime.now(UTC)
    suffix = ":".join(f"{value:02X}" for value in uuid4().bytes[:4])
    mac = f"02:00:{suffix}"

    first = repository.record_observation(
        DeviceObservation(
            source="integration-probe",
            observed_at=now,
            hostname="device-under-test",
            ip_address="192.0.2.20",
            mac_address=mac,
        )
    )
    second = repository.record_observation(
        DeviceObservation(
            source="integration-probe",
            observed_at=now + timedelta(seconds=10),
            hostname="device-under-test",
            ip_address="192.0.2.21",
            mac_address=mac,
        )
    )

    assert second.id == first.id
    assert second.ip_addresses == {"192.0.2.21"}
    assert second.mac_addresses == {mac}
