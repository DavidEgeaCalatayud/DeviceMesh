from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation, DeviceStatus
from app.domain.telemetry.models import Metric, MetricSample, TelemetryBatch
from app.infrastructure.database import (
    AgentRow,
    DeviceInterfaceRow,
    DeviceObservationRow,
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
            agent = session.get(AgentRow, agent_id)
            device = session.get(DeviceRow, agent.device_id) if agent is not None else None

            if device is None and agent is None:
                device = session.get(DeviceRow, agent_id)
            if device is None and identity is not None:
                device = self._resolve_identity_device(session, identity)
            if device is None:
                device = DeviceRow(
                    id=agent_id,
                    first_seen=timestamp,
                    status=DeviceStatus.UNKNOWN.value,
                )
                session.add(device)
                session.flush()

            device.status = DeviceStatus.ONLINE.value
            device.last_seen = timestamp
            if device.first_seen is None:
                device.first_seen = timestamp
            self._apply_identity(session, device, identity, timestamp)

            if agent is None:
                session.add(AgentRow(id=agent_id, device_id=device.id, last_seen=timestamp))
            else:
                agent.device_id = device.id
                agent.last_seen = timestamp

            session.commit()
            session.refresh(device)
            return self._to_domain(session, device)

    def record_observation(self, observation: DeviceObservation) -> Device:
        with self._session_factory() as session:
            device = self._resolve_observed_device(session, observation)
            if device is None:
                device = DeviceRow(
                    id=self._observation_device_id(observation),
                    hostname=observation.hostname,
                    manufacturer=observation.manufacturer,
                    status=DeviceStatus.ONLINE.value,
                    first_seen=observation.observed_at,
                    last_seen=observation.observed_at,
                )
                session.add(device)
                session.flush()
            else:
                device.hostname = observation.hostname or device.hostname
                device.manufacturer = observation.manufacturer or device.manufacturer
                device.status = DeviceStatus.ONLINE.value
                device.last_seen = observation.observed_at

            self._apply_observed_interface(session, device, observation)
            session.add(
                DeviceObservationRow(
                    device_id=device.id,
                    source=observation.source,
                    observed_at=observation.observed_at,
                    hostname=observation.hostname,
                    ip_address=observation.ip_address,
                    mac_address=(
                        _normalize_mac(observation.mac_address)
                        if observation.mac_address is not None
                        else None
                    ),
                    manufacturer=observation.manufacturer,
                    network_cidr=observation.network_cidr,
                    attributes=observation.attributes,
                )
            )
            latency = observation.attributes.get("latencyMs")
            if isinstance(latency, (int, float)) and not isinstance(latency, bool):
                session.add(
                    MetricSampleRow(
                        device_id=device.id,
                        metric_type="network.latency.ms",
                        timestamp=observation.observed_at,
                        value=float(latency),
                        unit="ms",
                    )
                )
            session.commit()
            session.refresh(device)
            return self._to_domain(session, device)

    def _resolve_identity_device(
        self,
        session: Session,
        identity: DeviceIdentity,
    ) -> DeviceRow | None:
        for raw_mac in identity.mac_addresses:
            mac = _normalize_mac(raw_mac)
            interface = session.scalar(
                select(DeviceInterfaceRow)
                .where(DeviceInterfaceRow.mac_address == mac)
                .limit(1)
            )
            if interface is not None:
                return session.get(DeviceRow, interface.device_id)

        if identity.hostname:
            device = session.scalar(
                select(DeviceRow)
                .where(DeviceRow.hostname == identity.hostname)
                .limit(1)
            )
            if device is not None:
                return device

        for raw_ip in identity.ip_addresses:
            ip = raw_ip.strip()
            if not ip:
                continue
            interface = session.scalar(
                select(DeviceInterfaceRow)
                .where(DeviceInterfaceRow.ip_address == ip)
                .limit(1)
            )
            if interface is not None:
                return session.get(DeviceRow, interface.device_id)
        return None

    def _resolve_observed_device(
        self,
        session: Session,
        observation: DeviceObservation,
    ) -> DeviceRow | None:
        if observation.mac_address:
            mac = _normalize_mac(observation.mac_address)
            interface = session.scalar(
                select(DeviceInterfaceRow)
                .where(DeviceInterfaceRow.mac_address == mac)
                .limit(1)
            )
            if interface is not None:
                return session.get(DeviceRow, interface.device_id)

        if observation.hostname:
            device = session.scalar(
                select(DeviceRow)
                .where(DeviceRow.hostname == observation.hostname)
                .limit(1)
            )
            if device is not None:
                return device

        if observation.ip_address:
            interface = session.scalar(
                select(DeviceInterfaceRow)
                .where(DeviceInterfaceRow.ip_address == observation.ip_address)
                .limit(1)
            )
            if interface is not None:
                return session.get(DeviceRow, interface.device_id)
        return None

    @staticmethod
    def _observation_device_id(observation: DeviceObservation) -> str:
        if observation.mac_address:
            key = f"mac:{_normalize_mac(observation.mac_address)}"
        elif observation.hostname:
            key = f"hostname:{observation.hostname.casefold()}"
        elif observation.ip_address:
            key = f"ip:{observation.ip_address}"
        else:
            key = f"source:{observation.source}:{observation.observed_at.isoformat()}"
        return f"discovered-{uuid5(NAMESPACE_URL, f'devicemesh:{key}')}"

    def _apply_observed_interface(
        self,
        session: Session,
        device: DeviceRow,
        observation: DeviceObservation,
    ) -> None:
        mac = _normalize_mac(observation.mac_address) if observation.mac_address else None
        row = None
        if mac is not None:
            row = session.scalar(
                select(DeviceInterfaceRow)
                .where(
                    DeviceInterfaceRow.device_id == device.id,
                    DeviceInterfaceRow.mac_address == mac,
                )
                .limit(1)
            )
        if row is None and observation.ip_address is not None:
            row = session.scalar(
                select(DeviceInterfaceRow)
                .where(
                    DeviceInterfaceRow.device_id == device.id,
                    DeviceInterfaceRow.ip_address == observation.ip_address,
                )
                .limit(1)
            )
        if row is None:
            session.add(
                DeviceInterfaceRow(
                    device_id=device.id,
                    mac_address=mac,
                    ip_address=observation.ip_address,
                    first_seen=observation.observed_at,
                    last_seen=observation.observed_at,
                )
            )
            return

        row.mac_address = mac or row.mac_address
        row.ip_address = observation.ip_address or row.ip_address
        row.last_seen = observation.observed_at

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
                session.flush()

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

    def list_latest(self) -> list[MetricSample]:
        rank = func.row_number().over(
            partition_by=(MetricSampleRow.device_id, MetricSampleRow.metric_type),
            order_by=(MetricSampleRow.timestamp.desc(), MetricSampleRow.id.desc()),
        ).label("sample_rank")
        ranked = select(
            MetricSampleRow.device_id.label("device_id"),
            MetricSampleRow.metric_type.label("metric_type"),
            MetricSampleRow.timestamp.label("timestamp"),
            MetricSampleRow.value.label("value"),
            MetricSampleRow.unit.label("unit"),
            rank,
        ).subquery()
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    ranked.c.device_id,
                    ranked.c.metric_type,
                    ranked.c.timestamp,
                    ranked.c.value,
                    ranked.c.unit,
                ).where(ranked.c.sample_rank == 1)
            ).all()
            return [
                MetricSample(
                    device_id=row.device_id,
                    timestamp=row.timestamp,
                    metric=Metric(row.metric_type, row.value, row.unit),
                )
                for row in rows
            ]
