from app.domain.network.models import InterfaceOperationalStatus
from app.infrastructure.snmp_poller import (
    _ARP_IP,
    _ARP_PHYS,
    _CDP_DEVICE_ID,
    _CDP_DEVICE_PORT,
    _IF_HC_IN,
    _IF_HC_OUT,
    _IF_HIGH_SPEED,
    _IF_IN_ERRORS,
    _IF_MTU,
    _IF_NAME,
    _IF_OPER,
    _IF_OUT_ERRORS,
    _IF_PHYS,
    _LLDP_REM_CHASSIS,
    _LLDP_REM_LOCAL_PORT,
    _LLDP_REM_PORT,
    _LLDP_REM_SYSNAME,
    _ROUTE_DEST,
    _ROUTE_IFINDEX,
    _ROUTE_MASK,
    _ROUTE_NEXTHOP,
    _ROUTE_TYPE,
    _VLAN_NAME,
    parse_snapshot,
)


def _walk(root: str, values: dict[str, str]) -> dict[str, str]:
    return {f"{root}.{suffix}": value for suffix, value in values.items()}


def test_parse_snmp_snapshot_builds_nms_inventory() -> None:
    values = {
        _IF_NAME: _walk(_IF_NAME, {"1": "Gi1/0/1"}),
        _IF_HIGH_SPEED: _walk(_IF_HIGH_SPEED, {"1": "1000"}),
        _IF_MTU: _walk(_IF_MTU, {"1": "1500"}),
        _IF_PHYS: _walk(_IF_PHYS, {"1": "00 11 22 33 44 55"}),
        _IF_OPER: _walk(_IF_OPER, {"1": "1"}),
        _IF_HC_IN: _walk(_IF_HC_IN, {"1": "100"}),
        _IF_HC_OUT: _walk(_IF_HC_OUT, {"1": "200"}),
        _IF_IN_ERRORS: _walk(_IF_IN_ERRORS, {"1": "2"}),
        _IF_OUT_ERRORS: _walk(_IF_OUT_ERRORS, {"1": "3"}),
        _LLDP_REM_LOCAL_PORT: _walk(_LLDP_REM_LOCAL_PORT, {"1.1.1": "1"}),
        _LLDP_REM_CHASSIS: _walk(_LLDP_REM_CHASSIS, {"1.1.1": "AA BB CC DD EE FF"}),
        _LLDP_REM_PORT: _walk(_LLDP_REM_PORT, {"1.1.1": "Gi0/48"}),
        _LLDP_REM_SYSNAME: _walk(_LLDP_REM_SYSNAME, {"1.1.1": "core-switch"}),
        _CDP_DEVICE_ID: _walk(_CDP_DEVICE_ID, {"1.1": "legacy-switch"}),
        _CDP_DEVICE_PORT: _walk(_CDP_DEVICE_PORT, {"1.1": "Gi0/1"}),
        _ROUTE_DEST: _walk(_ROUTE_DEST, {"10.0.0.0.255.255.255.0.0.10.0.0.1": "10.0.0.0"}),
        _ROUTE_MASK: _walk(_ROUTE_MASK, {"10.0.0.0.255.255.255.0.0.10.0.0.1": "255.255.255.0"}),
        _ROUTE_NEXTHOP: _walk(_ROUTE_NEXTHOP, {"10.0.0.0.255.255.255.0.0.10.0.0.1": "10.0.0.1"}),
        _ROUTE_IFINDEX: _walk(_ROUTE_IFINDEX, {"10.0.0.0.255.255.255.0.0.10.0.0.1": "1"}),
        _ROUTE_TYPE: _walk(_ROUTE_TYPE, {"10.0.0.0.255.255.255.0.0.10.0.0.1": "4"}),
        _ARP_PHYS: _walk(_ARP_PHYS, {"1.10.0.0.50": "DE AD BE EF 00 01"}),
        _ARP_IP: _walk(_ARP_IP, {"1.10.0.0.50": "10.0.0.50"}),
        _VLAN_NAME: _walk(_VLAN_NAME, {"120": "servers"}),
    }
    snapshot = parse_snapshot("edge-switch", values)

    assert snapshot.hostname == "edge-switch"
    assert snapshot.interfaces[0].name == "Gi1/0/1"
    assert snapshot.interfaces[0].operational_status is InterfaceOperationalStatus.UP
    assert snapshot.interfaces[0].speed_bps == 1_000_000_000
    assert snapshot.counters[0]["in_errors"] == 2
    assert {n["protocol"] for n in snapshot.neighbors} == {"lldp", "cdp"}
    assert snapshot.routes[0]["prefix_length"] == 24
    assert snapshot.arp_entries[0]["mac_address"] == "DE:AD:BE:EF:00:01"
    assert snapshot.vlans == [{"vlan_id": 120, "name": "servers"}]
