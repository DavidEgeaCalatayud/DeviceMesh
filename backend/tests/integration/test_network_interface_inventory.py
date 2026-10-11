from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.use_cases.record_observation import RecordObservation
from app.domain.devices.models import DeviceObservation
from app.domain.network.models import InterfaceOperationalStatus, ObservedNetworkInterface
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_interface_inventory_tracks_changes_disappearance_and_reappearance() -> None:
    device_repo = SqlAlchemyDeviceRepository(SessionFactory)
    network_repo = SqlAlchemyNetworkRepository(SessionFactory)
    use_case = RecordObservation(device_repo, network_repo)
    now = datetime.now(UTC)
    hostname = f"interfaces-{uuid4().hex[:8]}"
    mac = ":".join(f"{value:02X}" for value in uuid4().bytes[:6])

    def observation(at: datetime, interfaces: tuple[ObservedNetworkInterface, ...]) -> DeviceObservation:
        return DeviceObservation(
            source="agent-network-inventory",
            observed_at=at,
            hostname=hostname,
            ip_address="10.91.0.20",
            mac_address=mac,
            network_cidr="10.91.0.0/24",
            interfaces=interfaces,
            interface_snapshot_complete=True,
        )

    eth0 = ObservedNetworkInterface(
        name="eth0",
        mac_address=mac,
        operational_status=InterfaceOperationalStatus.UP,
        mtu=1500,
        speed_bps=1_000_000_000,
        vlan_id=120,
        ip_addresses=("10.91.0.20",),
        gateways=("10.91.0.1",),
        dns_servers=("1.1.1.1", "8.8.8.8"),
    )
    eth1 = ObservedNetworkInterface(
        name="eth1",
        operational_status=InterfaceOperationalStatus.DOWN,
        mtu=1500,
        speed_bps=100_000_000,
    )
    device = use_case.execute(observation(now, (eth0, eth1)))

    initial = {item.name: item for item in network_repo.list_interfaces(device_id=device.id)}
    assert set(initial) == {"eth0", "eth1"}
    assert initial["eth0"].vlan_id == 120
    assert initial["eth0"].ip_addresses == ("10.91.0.20",)
    assert initial["eth0"].last_changed_at == now

    unchanged_at = now + timedelta(seconds=30)
    use_case.execute(observation(unchanged_at, (eth0, eth1)))
    unchanged = {item.name: item for item in network_repo.list_interfaces(device_id=device.id)}
    assert unchanged["eth0"].last_seen == unchanged_at
    assert unchanged["eth0"].last_changed_at == now

    changed_at = now + timedelta(minutes=1)
    changed_eth0 = ObservedNetworkInterface(
        name="eth0",
        mac_address=mac,
        operational_status=InterfaceOperationalStatus.DOWN,
        mtu=9000,
        speed_bps=10_000_000_000,
        vlan_id=121,
        ip_addresses=("10.91.0.21",),
        gateways=("10.91.0.1",),
        dns_servers=("1.1.1.1",),
    )
    use_case.execute(observation(changed_at, (changed_eth0,)))

    present = network_repo.list_interfaces(device_id=device.id)
    assert [item.name for item in present] == ["eth0"]
    eth0_after = present[0]
    assert eth0_after.operational_status is InterfaceOperationalStatus.DOWN
    assert eth0_after.mtu == 9000
    assert eth0_after.speed_bps == 10_000_000_000
    assert eth0_after.vlan_id == 121
    assert eth0_after.last_changed_at == changed_at

    all_items = {item.name: item for item in network_repo.list_interfaces(device_id=device.id, present_only=False)}
    assert all_items["eth1"].present is False
    assert all_items["eth1"].last_changed_at == changed_at

    reappeared_at = now + timedelta(minutes=2)
    use_case.execute(observation(reappeared_at, (changed_eth0, eth1)))
    reappeared = {item.name: item for item in network_repo.list_interfaces(device_id=device.id)}
    assert reappeared["eth1"].present is True
    assert reappeared["eth1"].last_changed_at == reappeared_at
