from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.devices.models import DeviceObservation
from app.domain.network.models import (
    DeviceService,
    NetworkTopology,
    ServiceState,
    ServiceTransition,
    TopologyEdge,
    TopologyNode,
)
from app.infrastructure.database import DeviceObservationRow, DeviceRow, DeviceServiceRow


class SqlAlchemyNetworkRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

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
                    transitions.append(
                        ServiceTransition("SERVICE_EXPOSED", self._to_domain(row))
                    )
                    continue

                reopened = row.state != ServiceState.OPEN.value
                row.state = ServiceState.OPEN.value
                row.service_name = service.name or row.service_name
                row.last_seen = observation.observed_at
                row.source = observation.source
                row.network_cidr = observation.network_cidr or row.network_cidr
                if reopened:
                    row.last_changed_at = observation.observed_at
                    transitions.append(
                        ServiceTransition("SERVICE_EXPOSED", self._to_domain(row))
                    )

            if observation.service_snapshot_complete and scanned_tcp_ports:
                observed_tcp_ports = {
                    port for transport, port in observed if transport == "tcp"
                }
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
                        transitions.append(
                            ServiceTransition("SERVICE_CLOSED", self._to_domain(row))
                        )

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
        query = query.order_by(DeviceServiceRow.device_id, DeviceServiceRow.transport, DeviceServiceRow.port)
        with self._session_factory() as session:
            rows = session.scalars(query).all()
            return [self._to_domain(row) for row in rows]

    def get_topology(self) -> NetworkTopology:
        rank = func.row_number().over(
            partition_by=DeviceObservationRow.device_id,
            order_by=(DeviceObservationRow.observed_at.desc(), DeviceObservationRow.id.desc()),
        ).label("observation_rank")
        ranked = select(
            DeviceObservationRow.device_id.label("device_id"),
            DeviceObservationRow.network_cidr.label("network_cidr"),
            rank,
        ).where(DeviceObservationRow.network_cidr.is_not(None)).subquery()

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

        segments = sorted({row.network_cidr for row in memberships if row.network_cidr})
        nodes: list[TopologyNode] = [
            TopologyNode(
                id=f"network:{cidr}",
                kind="network",
                label=cidr,
                network_cidr=cidr,
            )
            for cidr in segments
        ]
        edges: list[TopologyEdge] = []
        linked_devices: set[str] = set()
        for membership in memberships:
            if not membership.network_cidr or membership.device_id not in devices:
                continue
            device = devices[membership.device_id]
            if device.id not in linked_devices:
                nodes.append(
                    TopologyNode(
                        id=f"device:{device.id}",
                        kind="device",
                        label=device.hostname or device.id,
                        device_id=device.id,
                        network_cidr=membership.network_cidr,
                        status=device.status,
                    )
                )
                linked_devices.add(device.id)
            edges.append(
                TopologyEdge(
                    source=f"network:{membership.network_cidr}",
                    target=f"device:{device.id}",
                )
            )
        return NetworkTopology(nodes=tuple(nodes), edges=tuple(edges))

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
