from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.devices.models import Device, DeviceIdentity, DeviceStatus
from app.domain.telemetry.models import TelemetryBatch
from app.infrastructure.database import (
    AgentRow,
    DeviceInterfaceRow,
    DeviceRow,
    MetricSampleRow,
)


def _normalize_mac(value: str) -> str:
    return value.strip().upper().replace("-", ":")


class SqlAlchemyDeviceRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_devices(self) -> list[Device]:
        with self._session_factory() as session:
            rows = session.scalars(select(DeviceRow).order_by(DeviceRow.id)).all()
            return [self._to_domain(session, row) for row in rows]

    def mark_agent_online(
        self,
        agent_id: str,
        timestamp: datetime,
        identity: DeviceIdentity | None = None,
    ) -> Device:
        with self._session_factory() as session:
            device = session.get(DeviceRow, agent_id)
            if device is None:
                device = DeviceRow(id=agent_id, first_seen=timestamp, status=DeviceStatus.UNKNOWN.value)
                session.add(device)

            device.status = DeviceStatus.ONLINE.value
            device.last_seen = timestamp
            if device.first_seen is None:
                device.first_seen = timestamp
            self._apply_identity(session, device, identity, timestamp)

            agent = session.get(AgentRow, agent_id)
            if agent is None:
                session.add(AgentRow(id=agent_id, device_id=device.id, last_seen=timestamp))
            else:
                agent.device_id = device.id
                agent.last_seen = timestamp

            session.commit()
            session.refresh(device)
            return self._to_domain(session, device)

    def _apply_identity(
        self,
        session: Session,
        device: DeviceRow,
        identity: DeviceIdentity | None,
        timestamp: datetime,
    ) -> None:
        if identity is None:
            return

        device.hostname = identity.hostname or device.hostname
        device.operating_system = identity.operating_system or device.operating_system
        device.operating_system_version = (
            identity.operating_system_version or device.operating_system_version
        )
        device.architecture = identity.architecture or device.architecture
        device.manufacturer = identity.manufacturer or device.manufacturer
        session.flush()

        existing = session.scalars(
            select(DeviceInterfaceRow).where(DeviceInterfaceRow.device_id == device.id)
        ).all()
        by_ip = {row.ip_address: row for row in existing if row.ip_address is not None}
        by_mac = {row.mac_address: row for row in existing if row.mac_address is not None}

        for raw_ip in identity.ip_addresses:
            ip = raw_ip.strip()
            if not ip:
                continue
            row = by_ip.get(ip)
            if row is None:
                session.add(
                    DeviceInterfaceRow(
                        device_id=device.id,
                        ip_address=ip,
                        first_seen=timestamp,
                        last_seen=timestamp,
                    )
                )
            else:
                row.last_seen = timestamp

        for raw_mac in identity.mac_addresses:
            mac = _normalize_mac(raw_mac)
            if not mac:
                continue
            row = by_mac.get(mac)
            if row is None:
                session.add(
                    DeviceInterfaceRow(
                        device_id=device.id,
                        mac_address=mac,
                        first_seen=timestamp,
                        last_seen=timestamp,
                    )
                )
            else:
                row.last_seen = timestamp

    @staticmethod
    def _to_domain(session: Session, row: DeviceRow) -> Device:
        interfaces = session.scalars(
            select(DeviceInterfaceRow).where(DeviceInterfaceRow.device_id == row.id)
        ).all()
        return Device(
            id=row.id,
            hostname=row.hostname,
            ip_addresses={item.ip_address for item in interfaces if item.ip_address is not None},
            mac_addresses={item.mac_address for item in interfaces if item.mac_address is not None},
            operating_system=row.operating_system,
            operating_system_version=row.operating_system_version,
            architecture=row.architecture,
            manufacturer=row.manufacturer,
            status=DeviceStatus(row.status),
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )


class SqlAlchemyTelemetryRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def append(self, batch: TelemetryBatch) -> None:
        with self._session_factory() as session:
            agent = session.get(AgentRow, batch.agent_id)
            device_id = agent.device_id if agent is not None else batch.agent_id

            device = session.get(DeviceRow, device_id)
            if device is None:
                device = DeviceRow(
                    id=device_id,
                    first_seen=batch.timestamp,
                    last_seen=batch.timestamp,
                    status=DeviceStatus.ONLINE.value,
                )
                session.add(device)

            if agent is None:
                session.add(
                    AgentRow(id=batch.agent_id, device_id=device_id, last_seen=batch.timestamp)
                )
            else:
                agent.last_seen = batch.timestamp

            device.last_seen = batch.timestamp
            for metric in batch.metrics:
                session.add(
                    MetricSampleRow(
                        device_id=device_id,
                        metric_type=metric.name,
                        timestamp=batch.timestamp,
                        value=metric.value,
                        unit=metric.unit,
                    )
                )
            session.commit()
