from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.devices.models import DeviceObservation
from app.domain.network.models import (
    DeviceService,
    InterfaceOperationalStatus,
    NetworkInterfaceInventory,
    NetworkTopology,
    ServiceState,
    ServiceTransition,
    TopologyEdge,
    TopologyNode,
)
from app.infrastructure.database import DeviceObservationRow, DeviceRow, DeviceServiceRow
from app.infrastructure.repositories.network_inventory import NetworkInterfaceInventoryRow
from app.infrastructure.repositories.nms import NetworkNeighborRow


def _normalize_mac(value: str | None) -> str | None:
    return value.strip().upper().replace("-", ":") if value else None


class SqlAlchemyNetworkRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def reconcile_interfaces(self, device_id: str, observation: DeviceObservation) -> None:
        if not observation.interfaces and not observation.interface_snapshot_complete:
            return

        observed = {item.name: item for item in observation.interfaces}
        with self._session_factory() as session:
            rows = session.scalars(
                select(NetworkInterfaceInventoryRow).where(
                    NetworkInterfaceInventoryRow.device_id == device_id
                )
            ).all()
            by_name = {row.interface_name: row for row in rows}

            for name, item in observed.items():
                row = by_name.get(name)
                mac = _normalize_mac(item.mac_address)
                addresses = list(item.ip_addresses)
                gateways = list(item.gateways)
                dns_servers = list(item.dns_servers)
                if row is None:
                    session.add(
                        NetworkInterfaceInventoryRow(
                            device_id=device_id,
                            interface_name=name,
                            mac_address=mac,
                            operational_status=item.operational_status.value,
                            mtu=item.mtu,
                            speed_bps=item.speed_bps,
                            vlan_id=item.vlan_id,
                            ip_addresses=addresses,
                            gateways=gateways,
                            dns_servers=dns_servers,
                            source=observation.source,
                            present=True,
                            first_seen=observation.observed_at,
                            last_seen=observation.observed_at,
                            last_changed_at=observation.observed_at,
                        )
                    )
                    continue

                changed = (
                    row.mac_address != mac
                    or row.operational_status != item.operational_status.value
                    or row.mtu != item.mtu
                    or row.speed_bps != item.speed_bps
                    or row.vlan_id != item.vlan_id
                    or row.ip_addresses != addresses
                    or row.gateways != gateways
                    or row.dns_servers != dns_servers
                    or not row.present
                )
                row.mac_address = mac
                row.operational_status = item.operational_status.value
                row.mtu = item.mtu
                row.speed_bps = item.speed_bps
                row.vlan_id = item.vlan_id
                row.ip_addresses = addresses
                row.gateways = gateways
                row.dns_servers = dns_servers
                row.source = observation.source
                row.present = True
                row.last_seen = observation.observed_at
                if changed:
                    row.last_changed_at = observation.observed_at

            if observation.interface_snapshot_complete:
                observed_names = set(observed)
                for row in rows:
                    if row.interface_name not in observed_names and row.present:
                        row.present = False
                        row.source = observation.source
                        row.last_seen = observation.observed_at
                        row.last_changed_at = observation.observed_at

            session.commit()

    def list_interfaces(
        self,
        *,
        device_id: str | None = None,
        present_only: bool = True,
    ) -> list[NetworkInterfaceInventory]:
        query = select(NetworkInterfaceInventoryRow)
        if device_id is not None:
            query = query.where(NetworkInterfaceInventoryRow.device_id == device_id)
        if present_only:
            query = query.where(NetworkInterfaceInventoryRow.present.is_(True))
        query = query.order_by(
            NetworkInterfaceInventoryRow.device_id,
            NetworkInterfaceInventoryRow.interface_name,
        )
        with self._session_factory() as session:
            return [self._interface_to_domain(row) for row in session.scalars(query).all()]

    def reconcile_services(
        self,
        device_id: str,
        observation: DeviceObservation,
    ) -> list[ServiceTransition]:
        if not observation.services and not observation.service_snapshot_complete:
            return []

        observed = {(service.transport, service.port): service for service in observation.services}
        scanned_tcp_ports = set(observation.scanned_tcp_ports)
        transitions: list[ServiceTransition] = []

        with self._session_factory() as session:
            rows = session.scalars(
                select(DeviceServiceRow).where(DeviceServiceRow.device_id == device_id)
            ).all()
            by_endpoint = {(row.transport, row.port): row for row in rows}

            for endpoint, service in observed.items():
                row = by_endpoint.get(endpoint)
                if row is None:
                    row = DeviceServiceRow(
                        device_id=device_id,
                        transport=service.transport,
                        port=service.port,
                        service_name=service.name,
                        state=ServiceState.OPEN.value,
                        first_seen=observation.observed_at,
                        last_seen=observation.observed_at,
                        last_changed_at=observation.observed_at,
                        source=observation.source,
                        network_cidr=observation.network_cidr,
                    )
                    session.add(row)
                    session.flush()
                    transitions.append(ServiceTransition("SERVICE_EXPOSED", self._to_domain(row)))
                    continue

                reopened = row.state != ServiceState.OPEN.value
                row.state = ServiceState.OPEN.value
                row.service_name = service.name or row.service_name
                row.last_seen = observation.observed_at
                row.source = observation.source
                row.network_cidr = observation.network_cidr or row.network_cidr
                if reopened:
                    row.last_changed_at = observation.observed_at
                    transitions.append(ServiceTransition("SERVICE_EXPOSED", self._to_domain(row)))

            if observation.service_snapshot_complete and scanned_tcp_ports:
                observed_tcp_ports = {port for transport, port in observed if transport == "tcp"}
                for row in rows:
                    if (
                        row.transport == "tcp"
                        and row.port in scanned_tcp_ports
                        and row.port not in observed_tcp_ports
                        and row.state == ServiceState.OPEN.value
                    ):
                        row.state = ServiceState.CLOSED.value
                        row.last_seen = observation.observed_at
                        row.last_changed_at = observation.observed_at
                        row.source = observation.source
                        row.network_cidr = observation.network_cidr or row.network_cidr
                        transitions.append(ServiceTransition("SERVICE_CLOSED", self._to_domain(row)))

            session.commit()
        return transitions

    def list_services(
        self,
        *,
        device_id: str | None = None,
        active_only: bool = True,
    ) -> list[DeviceService]:
        query = select(DeviceServiceRow)
        if device_id is not None:
            query = query.where(DeviceServiceRow.device_id == device_id)
        if active_only:
            query = query.where(DeviceServiceRow.state == ServiceState.OPEN.value)
        query = query.order_by(
            DeviceServiceRow.device_id,
            DeviceServiceRow.transport,
            DeviceServiceRow.port,
        )
        with self._session_factory() as session:
            rows = session.scalars(query).all()
            return [self._to_domain(row) for row in rows]

    def get_topology(self) -> NetworkTopology:
        rank = func.row_number().over(
            partition_by=DeviceObservationRow.device_id,
            order_by=(DeviceObservationRow.observed_at.desc(), DeviceObservationRow.id.desc()),
        ).label("observation_rank")
        ranked = (
            select(
                DeviceObservationRow.device_id.label("device_id"),
                DeviceObservationRow.network_cidr.label("network_cidr"),
                rank,
            )
            .where(DeviceObservationRow.network_cidr.is_not(None))
            .subquery()
        )

        with self._session_factory() as session:
            memberships = session.execute(
                select(ranked.c.device_id, ranked.c.network_cidr).where(
                    ranked.c.observation_rank == 1
                )
            ).all()
            devices = {
                row.id: row
                for row in session.scalars(select(DeviceRow).order_by(DeviceRow.id)).all()
            }
            physical = session.scalars(
                select(NetworkNeighborRow)
                .where(NetworkNeighborRow.present.is_(True))
                .order_by(
                    NetworkNeighborRow.device_id,
                    NetworkNeighborRow.local_interface,
                    NetworkNeighborRow.protocol,
                )
            ).all()

        physical_device_ids = {
            row.device_id for row in physical
        } | {
            row.remote_device_id for row in physical if row.remote_device_id is not None
        }
        nodes: list[TopologyNode] = []
        edges: list[TopologyEdge] = []
        added_nodes: set[str] = set()

        def add_device_node(device_id: str) -> None:
            node_id = f"device:{device_id}"
            if node_id in added_nodes:
                return
            device = devices.get(device_id)
            nodes.append(
                TopologyNode(
                    id=node_id,
                    kind="device",
                    label=(device.hostname if device is not None else None) or device_id,
                    device_id=device_id,
                    status=device.status if device is not None else None,
                )
            )
            added_nodes.add(node_id)

        for neighbor in physical:
            add_device_node(neighbor.device_id)
            if neighbor.remote_device_id is not None:
                add_device_node(neighbor.remote_device_id)
                target = f"device:{neighbor.remote_device_id}"
            else:
                identity = (
                    neighbor.remote_system_name
                    or neighbor.remote_chassis_id
                    or neighbor.remote_port_id
                    or "unknown"
                )
                target = (
                    "neighbor:"
                    + neighbor.protocol
                    + ":"
                    + neighbor.device_id
                    + ":"
                    + neighbor.local_interface
                    + ":"
                    + identity
                )
                if target not in added_nodes:
                    nodes.append(
                        TopologyNode(
                            id=target,
                            kind="neighbor",
                            label=identity,
                        )
                    )
                    added_nodes.add(target)
            edges.append(
                TopologyEdge(
                    source=f"device:{neighbor.device_id}",
                    target=target,
                    relation=neighbor.protocol,
                )
            )

        segments = sorted({row.network_cidr for row in memberships if row.network_cidr})
        for cidr in segments:
            node_id = f"network:{cidr}"
            if node_id not in added_nodes:
                nodes.append(
                    TopologyNode(
                        id=node_id,
                        kind="network",
                        label=cidr,
                        network_cidr=cidr,
                    )
                )
                added_nodes.add(node_id)

        for membership in memberships:
            if not membership.network_cidr or membership.device_id not in devices:
                continue
            if membership.device_id in physical_device_ids:
                continue
            add_device_node(membership.device_id)
            edges.append(
                TopologyEdge(
                    source=f"network:{membership.network_cidr}",
                    target=f"device:{membership.device_id}",
                    relation="observed-on",
                )
            )

        has_physical = bool(physical)
        has_fallback = any(edge.relation == "observed-on" for edge in edges)
        if has_physical:
            method = "lldp-cdp-with-segment-fallback" if has_fallback else "lldp-cdp"
        else:
            method = "observation-segment"
        return NetworkTopology(
            nodes=tuple(nodes),
            edges=tuple(edges),
            method=method,
            approximate=not has_physical or has_fallback,
        )

    @staticmethod
    def _interface_to_domain(row: NetworkInterfaceInventoryRow) -> NetworkInterfaceInventory:
        return NetworkInterfaceInventory(
            device_id=row.device_id,
            name=row.interface_name,
            mac_address=row.mac_address,
            operational_status=InterfaceOperationalStatus(row.operational_status),
            mtu=row.mtu,
            speed_bps=row.speed_bps,
            vlan_id=row.vlan_id,
            ip_addresses=tuple(row.ip_addresses),
            gateways=tuple(row.gateways),
            dns_servers=tuple(row.dns_servers),
            source=row.source,
            present=row.present,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
            last_changed_at=row.last_changed_at,
        )

    @staticmethod
    def _to_domain(row: DeviceServiceRow) -> DeviceService:
        return DeviceService(
            device_id=row.device_id,
            port=row.port,
            transport=row.transport,
            name=row.service_name,
            state=ServiceState(row.state),
            first_seen=row.first_seen,
            last_seen=row.last_seen,
            last_changed_at=row.last_changed_at,
            source=row.source,
            network_cidr=row.network_cidr,
        )
