from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.use_cases.record_observation import RecordObservation
from app.domain.devices.models import DeviceObservation
from app.domain.network.models import ObservedService, ServiceState
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.events import SqlAlchemyEventRepository
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_service_snapshot_opens_and_closes_once() -> None:
    device_repo = SqlAlchemyDeviceRepository(SessionFactory)
    network_repo = SqlAlchemyNetworkRepository(SessionFactory)
    event_repo = SqlAlchemyEventRepository(SessionFactory)
    use_case = RecordObservation(device_repo, network_repo, event_repo)
    now = datetime.now(UTC)
    hostname = f"service-{uuid4().hex[:8]}"
    mac = ":".join(f"{value:02X}" for value in uuid4().bytes[:6])

    def observation(at: datetime, services: tuple[ObservedService, ...]) -> DeviceObservation:
        return DeviceObservation(
            source="probe-test",
            observed_at=at,
            hostname=hostname,
            ip_address="10.77.0.10",
            mac_address=mac,
            network_cidr="10.77.0.0/24",
            services=services,
            service_snapshot_complete=True,
            scanned_tcp_ports=(22, 443),
        )

    device = use_case.execute(
        observation(
            now,
            (ObservedService(22, name="ssh"), ObservedService(443, name="https")),
        )
    )
    use_case.execute(
        observation(
            now + timedelta(seconds=1),
            (ObservedService(22, name="ssh"), ObservedService(443, name="https")),
        )
    )

    active = network_repo.list_services(device_id=device.id)
    assert {(service.port, service.state) for service in active} == {
        (22, ServiceState.OPEN),
        (443, ServiceState.OPEN),
    }

    use_case.execute(
        observation(
            now + timedelta(seconds=2),
            (ObservedService(443, name="https"),),
        )
    )
    all_services = network_repo.list_services(device_id=device.id, active_only=False)
    states = {service.port: service.state for service in all_services}
    assert states[22] is ServiceState.CLOSED
    assert states[443] is ServiceState.OPEN

    names = [
        event.name
        for event in event_repo.list_recent(100)
        if event.device_id == device.id and event.name.startswith("SERVICE_")
    ]
    assert names.count("SERVICE_EXPOSED") == 2
    assert names.count("SERVICE_CLOSED") == 1


def test_topology_groups_latest_device_observation_by_network() -> None:
    device_repo = SqlAlchemyDeviceRepository(SessionFactory)
    network_repo = SqlAlchemyNetworkRepository(SessionFactory)
    now = datetime.now(UTC)
    hostname = f"topology-{uuid4().hex[:8]}"
    device = device_repo.record_observation(
        DeviceObservation(
            source="probe-test",
            observed_at=now,
            hostname=hostname,
            ip_address="10.78.0.20",
            network_cidr="10.78.0.0/24",
        )
    )

    topology = network_repo.get_topology()
    assert topology.approximate is True
    assert topology.method == "observation-segment"
    assert any(node.id == "network:10.78.0.0/24" for node in topology.nodes)
    assert any(node.device_id == device.id for node in topology.nodes)
    assert any(
        edge.source == "network:10.78.0.0/24" and edge.target == f"device:{device.id}"
        for edge in topology.edges
    )
