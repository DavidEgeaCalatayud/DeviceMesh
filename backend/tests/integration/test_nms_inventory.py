from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.devices.models import DeviceObservation
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.infrastructure.repositories.nms import SqlAlchemyNmsRepository
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_nms_target_inventory_and_physical_topology_lifecycle() -> None:
    device_repo = SqlAlchemyDeviceRepository(SessionFactory)
    network_repo = SqlAlchemyNetworkRepository(SessionFactory)
    nms_repo = SqlAlchemyNmsRepository(SessionFactory)
    now = datetime.now(UTC)

    edge_mac = "02:10:20:30:40:50"
    core_mac = "02:AA:BB:CC:DD:EE"
    edge = device_repo.record_observation(
        DeviceObservation(
            source="test",
            observed_at=now,
            hostname=f"edge-{uuid4().hex[:8]}",
            ip_address="10.94.0.10",
            mac_address=edge_mac,
            network_cidr="10.94.0.0/24",
        )
    )
    core = device_repo.record_observation(
        DeviceObservation(
            source="test",
            observed_at=now,
            hostname=f"core-{uuid4().hex[:8]}",
            ip_address="10.94.0.1",
            mac_address=core_mac,
            network_cidr="10.94.0.0/24",
        )
    )

    target = nms_repo.create_target(
        device_id=edge.id,
        address="10.94.0.10",
        port=161,
        username="nms-reader",
        auth_secret_ref="edge-snmp-auth",
        interval_seconds=60,
    )
    assert target.auth_secret_ref == "edge-snmp-auth"
    assert target.address == "10.94.0.10"
    assert nms_repo.due_targets(now)[0].id == target.id

    nms_repo.reconcile_neighbors(
        edge.id,
        now,
        [
            {
                "local_interface": "Gi1/0/48",
                "protocol": "lldp",
                "remote_chassis_id": core_mac,
                "remote_system_name": core.hostname,
                "remote_port_id": "Gi1/0/1",
            }
        ],
    )
    neighbors = nms_repo.list_neighbors(device_id=edge.id)
    assert len(neighbors) == 1
    assert neighbors[0].remote_device_id == core.id

    topology = network_repo.get_topology()
    assert topology.method in {"lldp-cdp", "lldp-cdp-with-segment-fallback"}
    assert any(
        edge_item.source == f"device:{edge.id}"
        and edge_item.target == f"device:{core.id}"
        and edge_item.relation == "lldp"
        for edge_item in topology.edges
    )
    assert not any(
        edge_item.target == f"device:{edge.id}" and edge_item.relation == "observed-on"
        for edge_item in topology.edges
    )

    changed_at = now + timedelta(minutes=1)
    nms_repo.reconcile_neighbors(edge.id, changed_at, [])
    assert nms_repo.list_neighbors(device_id=edge.id) == []
    historical = nms_repo.list_neighbors(device_id=edge.id, present_only=False)
    assert len(historical) == 1
    assert historical[0].present is False
    assert historical[0].last_changed_at == changed_at

    nms_repo.mark_poll_result(target.id, changed_at, "poll_failed")
    updated = nms_repo.list_targets()[0]
    assert updated.last_polled_at == changed_at
    assert updated.last_error == "poll_failed"
    assert nms_repo.due_targets(changed_at + timedelta(seconds=59)) == []
    assert nms_repo.due_targets(changed_at + timedelta(seconds=60))[0].id == target.id


def test_nms_snapshots_preserve_historical_routes_arp_vlan_and_counters() -> None:
    device_repo = SqlAlchemyDeviceRepository(SessionFactory)
    nms_repo = SqlAlchemyNmsRepository(SessionFactory)
    now = datetime.now(UTC)
    device = device_repo.record_observation(
        DeviceObservation(
            source="test",
            observed_at=now,
            hostname=f"router-{uuid4().hex[:8]}",
            ip_address="10.95.0.1",
            mac_address="02:01:02:03:04:05",
            network_cidr="10.95.0.0/24",
        )
    )

    nms_repo.replace_routes(
        device.id,
        now,
        [
            {
                "destination": "10.95.0.0",
                "prefix_length": 24,
                "next_hop": "0.0.0.0",
                "interface_name": "Gi0/1",
                "route_type": "3",
            }
        ],
    )
    nms_repo.replace_arp(
        device.id,
        now,
        [
            {
                "interface_name": "Gi0/1",
                "ip_address": "10.95.0.20",
                "mac_address": "02:20:20:20:20:20",
            }
        ],
    )
    nms_repo.replace_vlans(device.id, now, [{"vlan_id": 120, "name": "servers"}])
    nms_repo.append_interface_samples(
        device.id,
        now,
        [
            {
                "interface_name": "Gi0/1",
                "in_octets": 1000,
                "out_octets": 2000,
                "in_errors": 1,
                "out_errors": 2,
            }
        ],
    )

    assert nms_repo.list_routes(device_id=device.id)[0].prefix_length == 24
    assert nms_repo.list_arp(device_id=device.id)[0].ip_address == "10.95.0.20"
    assert nms_repo.list_vlans(device_id=device.id)[0].vlan_id == 120
    assert nms_repo.list_interface_samples(device.id)[0].out_octets == 2000

    later = now + timedelta(minutes=1)
    nms_repo.replace_routes(device.id, later, [])
    nms_repo.replace_arp(device.id, later, [])
    nms_repo.replace_vlans(device.id, later, [])
    assert nms_repo.list_routes(device_id=device.id) == []
    assert nms_repo.list_arp(device_id=device.id) == []
    assert nms_repo.list_vlans(device_id=device.id) == []
    assert nms_repo.list_routes(device_id=device.id, present_only=False)[0].present is False
    assert nms_repo.list_arp(device_id=device.id, present_only=False)[0].present is False
    assert nms_repo.list_vlans(device_id=device.id, present_only=False)[0].present is False
