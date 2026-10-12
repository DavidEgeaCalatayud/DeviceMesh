from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceObservation
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository
from app.infrastructure.repositories.syslog import SqlAlchemySyslogRepository


def test_syslog_persistence_search_correlation_and_retention() -> None:
    devices = SqlAlchemyDeviceRepository(SessionFactory)
    repository = SqlAlchemySyslogRepository(SessionFactory)
    now = datetime.now(UTC)
    hostname = f"syslog-{uuid4().hex[:8]}"
    device = devices.record_observation(
        DeviceObservation(
            source="test",
            observed_at=now,
            hostname=hostname,
            ip_address="10.96.0.10",
            mac_address="02:96:00:00:00:10",
            network_cidr="10.96.0.0/24",
        )
    )
    row = repository.append(
        received_at=now,
        source_address="10.96.0.10",
        facility=16,
        severity=3,
        hostname=hostname,
        app_name="linkd",
        proc_id="42",
        msg_id="LINK_DOWN",
        message="uplink Gi1/0/48 failed",
        protocol="rfc5424",
    )
    assert row.device_id == device.id

    assert repository.search(device_id=device.id)[0].id == row.id
    assert repository.search(severity=3)[0].id == row.id
    assert repository.search(facility=16)[0].id == row.id
    assert repository.search(query_text="Gi1/0/48")[0].id == row.id
    assert repository.search(query_text="does-not-exist") == []

    assert repository.delete_before(now - timedelta(seconds=1)) == 0
    assert repository.delete_before(now + timedelta(seconds=1)) == 1
    assert repository.search(device_id=device.id) == []
