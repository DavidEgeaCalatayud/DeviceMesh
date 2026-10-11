from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import ip_address
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.nms import (
    ArpEntry,
    InterfaceCounterSample,
    NetworkManagementTarget,
    NetworkNeighbor,
    NetworkRoute,
    SnmpAuthProtocol,
    VlanInventory,
)
from app.infrastructure.database import Base, DeviceInterfaceRow, DeviceRow


class NetworkManagementTargetRow(Base):
    __tablename__ = "network_management_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False, unique=True)
    address: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=161)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    auth_protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    auth_secret_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(128))


class NetworkNeighborRow(Base):
    __tablename__ = "network_neighbors"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "local_interface",
            "protocol",
            "remote_chassis_id",
            "remote_port_id",
            name="uq_network_neighbor_link",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    local_interface: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    remote_chassis_id: Mapped[str | None] = mapped_column(String(255))
    remote_system_name: Mapped[str | None] = mapped_column(String(255))
    remote_port_id: Mapped[str | None] = mapped_column(String(255))
    remote_device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkRouteRow(Base):
    __tablename__ = "network_routes"
    __table_args__ = (
        UniqueConstraint("device_id", "destination", "prefix_length", "next_hop", name="uq_network_route"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    destination: Mapped[str] = mapped_column(String(64), nullable=False)
    prefix_length: Mapped[int] = mapped_column(Integer, nullable=False)
    next_hop: Mapped[str | None] = mapped_column(String(64))
    interface_name: Mapped[str | None] = mapped_column(String(128))
    route_type: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkArpRow(Base):
    __tablename__ = "network_arp_entries"
    __table_args__ = (
        UniqueConstraint("device_id", "ip_address", name="uq_network_arp_device_ip"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    interface_name: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    mac_address: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkVlanRow(Base):
    __tablename__ = "network_vlans"
    __table_args__ = (
        UniqueConstraint("device_id", "vlan_id", name="uq_network_vlan_device_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    vlan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NetworkInterfaceCounterRow(Base):
    __tablename__ = "network_interface_counters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    interface_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    in_octets: Mapped[int | None] = mapped_column(BigInteger)
    out_octets: Mapped[int | None] = mapped_column(BigInteger)
    in_errors: Mapped[int | None] = mapped_column(BigInteger)
    out_errors: Mapped[int | None] = mapped_column(BigInteger)


class SqlAlchemyNmsRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_target(
        self,
        *,
        device_id: str,
        address: str,
        port: int,
        username: str,
        auth_secret_ref: str,
        interval_seconds: int,
    ) -> NetworkManagementTarget:
        normalized_address = str(ip_address(address))
        with self._session_factory.begin() as session:
            if session.get(DeviceRow, device_id) is None:
                raise ValueError("NMS target device does not exist")
            if session.scalar(
                select(NetworkManagementTargetRow).where(
                    NetworkManagementTargetRow.device_id == device_id
                )
            ) is not None:
                raise ValueError("NMS target already exists for device")
            row = NetworkManagementTargetRow(
                id=str(uuid4()),
                device_id=device_id,
                address=normalized_address,
                port=port,
                username=username,
                auth_protocol=SnmpAuthProtocol.SHA256.value,
                auth_secret_ref=auth_secret_ref,
                interval_seconds=interval_seconds,
                enabled=True,
            )
            session.add(row)
            session.flush()
            return self._target(row)

    def list_targets(self, *, enabled_only: bool = False) -> list[NetworkManagementTarget]:
        query = select(NetworkManagementTargetRow)
        if enabled_only:
            query = query.where(NetworkManagementTargetRow.enabled.is_(True))
        query = query.order_by(NetworkManagementTargetRow.device_id)
        with self._session_factory() as session:
            return [self._target(row) for row in session.scalars(query).all()]

    def set_target_state(self, target_id: str, enabled: bool) -> NetworkManagementTarget:
        with self._session_factory.begin() as session:
            row = session.get(NetworkManagementTargetRow, target_id)
            if row is None:
                raise KeyError(target_id)
            row.enabled = enabled
            session.flush()
            return self._target(row)

    def due_targets(self, now: datetime, *, limit: int = 50) -> list[NetworkManagementTarget]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(NetworkManagementTargetRow)
                .where(NetworkManagementTargetRow.enabled.is_(True))
                .order_by(NetworkManagementTargetRow.last_polled_at.asc().nullsfirst())
                .limit(limit * 4)
            ).all()
            due = [
                row
                for row in rows
                if row.last_polled_at is None
                or row.last_polled_at + timedelta(seconds=row.interval_seconds) <= now
            ]
            return [self._target(row) for row in due[:limit]]

    def mark_poll_result(self, target_id: str, at: datetime, error: str | None) -> None:
        with self._session_factory.begin() as session:
            row = session.get(NetworkManagementTargetRow, target_id)
            if row is None:
                return
            row.last_polled_at = at
            row.last_error = error[:128] if error else None

    def reconcile_neighbors(
        self,
        device_id: str,
        at: datetime,
        neighbors: list[dict[str, str | None]],
    ) -> None:
        with self._session_factory.begin() as session:
            existing = list(
                session.scalars(
                    select(NetworkNeighborRow).where(NetworkNeighborRow.device_id == device_id)
                ).all()
            )
            matched: set[int] = set()
            for item in neighbors:
                row = next(
                    (
                        candidate
                        for candidate in existing
                        if candidate.local_interface == item["local_interface"]
                        and candidate.protocol == item["protocol"]
                        and candidate.remote_chassis_id == item.get("remote_chassis_id")
                        and candidate.remote_port_id == item.get("remote_port_id")
                    ),
                    None,
                )
                remote_device_id = self._resolve_remote_device(
                    session,
                    item.get("remote_chassis_id"),
                    item.get("remote_system_name"),
                )
                if row is None:
                    row = NetworkNeighborRow(
                        device_id=device_id,
                        local_interface=str(item["local_interface"]),
                        protocol=str(item["protocol"]),
                        remote_chassis_id=item.get("remote_chassis_id"),
                        remote_system_name=item.get("remote_system_name"),
                        remote_port_id=item.get("remote_port_id"),
                        remote_device_id=remote_device_id,
                        present=True,
                        first_seen=at,
                        last_seen=at,
                        last_changed_at=at,
                    )
                    session.add(row)
                    session.flush()
                    existing.append(row)
                else:
                    changed = (
                        not row.present
                        or row.remote_system_name != item.get("remote_system_name")
                        or row.remote_device_id != remote_device_id
                    )
                    row.remote_system_name = item.get("remote_system_name")
                    row.remote_device_id = remote_device_id
                    row.present = True
                    row.last_seen = at
                    if changed:
                        row.last_changed_at = at
                matched.add(row.id)
            for row in existing:
                if row.id not in matched and row.present:
                    row.present = False
                    row.last_seen = at
                    row.last_changed_at = at

    def replace_routes(self, device_id: str, at: datetime, routes: list[dict[str, object]]) -> None:
        with self._session_factory.begin() as session:
            rows = list(
                session.scalars(
                    select(NetworkRouteRow).where(NetworkRouteRow.device_id == device_id)
                ).all()
            )
            seen: set[tuple[str, int, str | None]] = set()
            for item in routes:
                key = (
                    str(item["destination"]),
                    self._required_int(item["prefix_length"]),
                    str(item["next_hop"]) if item.get("next_hop") else None,
                )
                seen.add(key)
                row = next(
                    (
                        x
                        for x in rows
                        if (x.destination, x.prefix_length, x.next_hop) == key
                    ),
                    None,
                )
                if row is None:
                    row = NetworkRouteRow(
                        device_id=device_id,
                        destination=key[0],
                        prefix_length=key[1],
                        next_hop=key[2],
                        interface_name=str(item["interface_name"]) if item.get("interface_name") else None,
                        route_type=str(item["route_type"]) if item.get("route_type") else None,
                        source="snmpv3",
                        present=True,
                        first_seen=at,
                        last_seen=at,
                    )
                    session.add(row)
                    rows.append(row)
                else:
                    row.interface_name = (
                        str(item["interface_name"]) if item.get("interface_name") else None
                    )
                    row.route_type = str(item["route_type"]) if item.get("route_type") else None
                    row.present = True
                    row.last_seen = at
            for row in rows:
                if (row.destination, row.prefix_length, row.next_hop) not in seen:
                    row.present = False
                    row.last_seen = at

    def replace_arp(self, device_id: str, at: datetime, entries: list[dict[str, str | None]]) -> None:
        with self._session_factory.begin() as session:
            rows = list(
                session.scalars(
                    select(NetworkArpRow).where(NetworkArpRow.device_id == device_id)
                ).all()
            )
            seen: set[str] = set()
            for item in entries:
                ip_value = str(item["ip_address"])
                seen.add(ip_value)
                row = next((x for x in rows if x.ip_address == ip_value), None)
                if row is None:
                    row = NetworkArpRow(
                        device_id=device_id,
                        interface_name=item.get("interface_name"),
                        ip_address=ip_value,
                        mac_address=str(item["mac_address"]),
                        source="snmpv3",
                        present=True,
                        first_seen=at,
                        last_seen=at,
                    )
                    session.add(row)
                    rows.append(row)
                else:
                    row.interface_name = item.get("interface_name")
                    row.mac_address = str(item["mac_address"])
                    row.present = True
                    row.last_seen = at
            for row in rows:
                if row.ip_address not in seen:
                    row.present = False
                    row.last_seen = at

    def replace_vlans(self, device_id: str, at: datetime, vlans: list[dict[str, object]]) -> None:
        with self._session_factory.begin() as session:
            rows = list(
                session.scalars(
                    select(NetworkVlanRow).where(NetworkVlanRow.device_id == device_id)
                ).all()
            )
            seen: set[int] = set()
            for item in vlans:
                vlan_id = self._required_int(item["vlan_id"])
                seen.add(vlan_id)
                row = next((x for x in rows if x.vlan_id == vlan_id), None)
                if row is None:
                    row = NetworkVlanRow(
                        device_id=device_id,
                        vlan_id=vlan_id,
                        name=str(item["name"]) if item.get("name") else None,
                        source="snmpv3",
                        present=True,
                        first_seen=at,
                        last_seen=at,
                    )
                    session.add(row)
                    rows.append(row)
                else:
                    row.name = str(item["name"]) if item.get("name") else None
                    row.present = True
                    row.last_seen = at
            for row in rows:
                if row.vlan_id not in seen:
                    row.present = False
                    row.last_seen = at

    def append_interface_samples(
        self,
        device_id: str,
        at: datetime,
        samples: list[dict[str, object]],
    ) -> None:
        with self._session_factory.begin() as session:
            for item in samples:
                session.add(
                    NetworkInterfaceCounterRow(
                        device_id=device_id,
                        interface_name=str(item["interface_name"]),
                        sampled_at=at,
                        in_octets=self._optional_int(item.get("in_octets")),
                        out_octets=self._optional_int(item.get("out_octets")),
                        in_errors=self._optional_int(item.get("in_errors")),
                        out_errors=self._optional_int(item.get("out_errors")),
                    )
                )

    def list_neighbors(self, *, device_id: str | None = None, present_only: bool = True) -> list[NetworkNeighbor]:
        query = select(NetworkNeighborRow)
        if device_id:
            query = query.where(NetworkNeighborRow.device_id == device_id)
        if present_only:
            query = query.where(NetworkNeighborRow.present.is_(True))
        with self._session_factory() as session:
            return [self._neighbor(row) for row in session.scalars(query.order_by(NetworkNeighborRow.device_id, NetworkNeighborRow.local_interface)).all()]

    def list_routes(self, *, device_id: str | None = None, present_only: bool = True) -> list[NetworkRoute]:
        query = select(NetworkRouteRow)
        if device_id:
            query = query.where(NetworkRouteRow.device_id == device_id)
        if present_only:
            query = query.where(NetworkRouteRow.present.is_(True))
        with self._session_factory() as session:
            return [self._route(row) for row in session.scalars(query.order_by(NetworkRouteRow.device_id, NetworkRouteRow.destination)).all()]

    def list_arp(self, *, device_id: str | None = None, present_only: bool = True) -> list[ArpEntry]:
        query = select(NetworkArpRow)
        if device_id:
            query = query.where(NetworkArpRow.device_id == device_id)
        if present_only:
            query = query.where(NetworkArpRow.present.is_(True))
        with self._session_factory() as session:
            return [self._arp(row) for row in session.scalars(query.order_by(NetworkArpRow.device_id, NetworkArpRow.ip_address)).all()]

    def list_vlans(self, *, device_id: str | None = None, present_only: bool = True) -> list[VlanInventory]:
        query = select(NetworkVlanRow)
        if device_id:
            query = query.where(NetworkVlanRow.device_id == device_id)
        if present_only:
            query = query.where(NetworkVlanRow.present.is_(True))
        with self._session_factory() as session:
            return [self._vlan(row) for row in session.scalars(query.order_by(NetworkVlanRow.device_id, NetworkVlanRow.vlan_id)).all()]

    def list_interface_samples(self, device_id: str, *, limit: int = 500) -> list[InterfaceCounterSample]:
        bounded = min(max(limit, 1), 5000)
        with self._session_factory() as session:
            rows = session.scalars(
                select(NetworkInterfaceCounterRow)
                .where(NetworkInterfaceCounterRow.device_id == device_id)
                .order_by(NetworkInterfaceCounterRow.sampled_at.desc(), NetworkInterfaceCounterRow.id.desc())
                .limit(bounded)
            ).all()
            return [
                InterfaceCounterSample(
                    device_id=row.device_id,
                    interface_name=row.interface_name,
                    sampled_at=row.sampled_at,
                    in_octets=row.in_octets,
                    out_octets=row.out_octets,
                    in_errors=row.in_errors,
                    out_errors=row.out_errors,
                )
                for row in rows
            ]

    @staticmethod
    def _resolve_remote_device(session: Session, chassis: str | None, system_name: str | None) -> str | None:
        if chassis:
            normalized = chassis.strip().upper().replace("-", ":")
            iface = session.scalar(
                select(DeviceInterfaceRow).where(DeviceInterfaceRow.mac_address == normalized).limit(1)
            )
            if iface is not None:
                return iface.device_id
        if system_name:
            device = session.scalar(
                select(DeviceRow).where(DeviceRow.hostname == system_name).limit(1)
            )
            if device is not None:
                return device.id
        return None

    @staticmethod
    def _required_int(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise TypeError("NMS integer value must be an integer or numeric string")
        return int(value)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise TypeError("NMS counter value must be an integer or numeric string")
        return int(value)

    @staticmethod
    def _target(row: NetworkManagementTargetRow) -> NetworkManagementTarget:
        return NetworkManagementTarget(
            id=row.id,
            device_id=row.device_id,
            address=row.address,
            port=row.port,
            username=row.username,
            auth_protocol=SnmpAuthProtocol(row.auth_protocol),
            auth_secret_ref=row.auth_secret_ref,
            interval_seconds=row.interval_seconds,
            enabled=row.enabled,
            last_polled_at=row.last_polled_at,
            last_error=row.last_error,
        )

    @staticmethod
    def _neighbor(row: NetworkNeighborRow) -> NetworkNeighbor:
        return NetworkNeighbor(
            device_id=row.device_id,
            local_interface=row.local_interface,
            protocol=row.protocol,
            remote_chassis_id=row.remote_chassis_id,
            remote_system_name=row.remote_system_name,
            remote_port_id=row.remote_port_id,
            remote_device_id=row.remote_device_id,
            present=row.present,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
            last_changed_at=row.last_changed_at,
        )

    @staticmethod
    def _route(row: NetworkRouteRow) -> NetworkRoute:
        return NetworkRoute(
            device_id=row.device_id,
            destination=row.destination,
            prefix_length=row.prefix_length,
            next_hop=row.next_hop,
            interface_name=row.interface_name,
            route_type=row.route_type,
            source=row.source,
            present=row.present,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )

    @staticmethod
    def _arp(row: NetworkArpRow) -> ArpEntry:
        return ArpEntry(
            device_id=row.device_id,
            interface_name=row.interface_name,
            ip_address=row.ip_address,
            mac_address=row.mac_address,
            source=row.source,
            present=row.present,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )

    @staticmethod
    def _vlan(row: NetworkVlanRow) -> VlanInventory:
        return VlanInventory(
            device_id=row.device_id,
            vlan_id=row.vlan_id,
            name=row.name,
            source=row.source,
            present=row.present,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
        )
