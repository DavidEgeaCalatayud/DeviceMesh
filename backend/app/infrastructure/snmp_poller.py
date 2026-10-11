from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Network

from pysnmp.hlapi.v3arch.asyncio import (
    USM_AUTH_HMAC192_SHA256,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    get_cmd,
)

from app.domain.devices.models import DeviceObservation
from app.domain.network.models import InterfaceOperationalStatus, ObservedNetworkInterface
from app.domain.nms import NetworkManagementTarget
from app.infrastructure.nms_secrets import NmsSecretResolver
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.infrastructure.repositories.nms import SqlAlchemyNmsRepository

_SYS_NAME = "1.3.6.1.2.1.1.5.0"
_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"
_IF_HC_IN = "1.3.6.1.2.1.31.1.1.1.6"
_IF_HC_OUT = "1.3.6.1.2.1.31.1.1.1.10"
_IF_MTU = "1.3.6.1.2.1.2.2.1.4"
_IF_PHYS = "1.3.6.1.2.1.2.2.1.6"
_IF_OPER = "1.3.6.1.2.1.2.2.1.8"
_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
_IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"
_LLDP_REM_LOCAL_PORT = "1.0.8802.1.1.2.1.4.1.1.2"
_LLDP_REM_CHASSIS = "1.0.8802.1.1.2.1.4.1.1.5"
_LLDP_REM_PORT = "1.0.8802.1.1.2.1.4.1.1.7"
_LLDP_REM_SYSNAME = "1.0.8802.1.1.2.1.4.1.1.9"
_CDP_DEVICE_ID = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
_CDP_DEVICE_PORT = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"
_ROUTE_DEST = "1.3.6.1.2.1.4.24.4.1.1"
_ROUTE_MASK = "1.3.6.1.2.1.4.24.4.1.2"
_ROUTE_NEXTHOP = "1.3.6.1.2.1.4.24.4.1.4"
_ROUTE_IFINDEX = "1.3.6.1.2.1.4.24.4.1.5"
_ROUTE_TYPE = "1.3.6.1.2.1.4.24.4.1.6"
_ARP_PHYS = "1.3.6.1.2.1.4.22.1.2"
_ARP_IP = "1.3.6.1.2.1.4.22.1.3"
_VLAN_NAME = "1.3.6.1.2.1.17.7.1.4.3.1.1"


@dataclass(frozen=True, slots=True)
class SnmpSnapshot:
    hostname: str | None
    interfaces: tuple[ObservedNetworkInterface, ...]
    counters: list[dict[str, object]]
    neighbors: list[dict[str, str | None]]
    routes: list[dict[str, object]]
    arp_entries: list[dict[str, str | None]]
    vlans: list[dict[str, object]]


class SnmpV3Client:
    async def poll(self, target: NetworkManagementTarget, auth_key: str) -> SnmpSnapshot:
        engine = SnmpEngine()
        auth = UsmUserData(
            target.username,
            authKey=auth_key,
            authProtocol=USM_AUTH_HMAC192_SHA256,
        )
        transport = await UdpTransportTarget.create(
            (target.address, target.port),
            timeout=5,
            retries=1,
        )
        hostname = await self._get(engine, auth, transport, _SYS_NAME)
        roots = (
            _IF_NAME,
            _IF_HIGH_SPEED,
            _IF_HC_IN,
            _IF_HC_OUT,
            _IF_MTU,
            _IF_PHYS,
            _IF_OPER,
            _IF_IN_ERRORS,
            _IF_OUT_ERRORS,
            _LLDP_REM_LOCAL_PORT,
            _LLDP_REM_CHASSIS,
            _LLDP_REM_PORT,
            _LLDP_REM_SYSNAME,
            _CDP_DEVICE_ID,
            _CDP_DEVICE_PORT,
            _ROUTE_DEST,
            _ROUTE_MASK,
            _ROUTE_NEXTHOP,
            _ROUTE_IFINDEX,
            _ROUTE_TYPE,
            _ARP_PHYS,
            _ARP_IP,
            _VLAN_NAME,
        )
        values = {root: await self._walk(engine, auth, transport, root) for root in roots}
        return parse_snapshot(hostname, values)

    async def _get(self, engine: SnmpEngine, auth: UsmUserData, transport: UdpTransportTarget, oid: str) -> str | None:
        error, status, _, var_binds = await get_cmd(
            engine,
            auth,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error:
            raise RuntimeError("SNMP request failed")
        if status:
            raise RuntimeError("SNMP agent returned an error")
        if not var_binds:
            return None
        return var_binds[0][1].prettyPrint()

    async def _walk(
        self,
        engine: SnmpEngine,
        auth: UsmUserData,
        transport: UdpTransportTarget,
        root: str,
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        async for error, status, _, var_binds in bulk_walk_cmd(
            engine,
            auth,
            transport,
            ContextData(),
            0,
            25,
            ObjectType(ObjectIdentity(root)),
            lexicographicMode=False,
        ):
            if error:
                raise RuntimeError("SNMP walk failed")
            if status:
                raise RuntimeError("SNMP agent returned an error")
            for var_bind in var_binds:
                oid = var_bind[0].prettyPrint()
                result[oid] = var_bind[1].prettyPrint()
        return result


class NetworkPollWorker:
    def __init__(
        self,
        nms_repository: SqlAlchemyNmsRepository,
        network_repository: SqlAlchemyNetworkRepository,
        resolver: NmsSecretResolver,
        client: SnmpV3Client | None = None,
    ) -> None:
        self._nms = nms_repository
        self._network = network_repository
        self._resolver = resolver
        self._client = client or SnmpV3Client()

    def run_due(self, now: datetime) -> tuple[int, int]:
        succeeded = 0
        failed = 0
        for target in self._nms.due_targets(now):
            try:
                auth_key = self._resolver.resolve(target.auth_secret_ref)
                snapshot = asyncio.run(self._client.poll(target, auth_key))
                self._network.reconcile_interfaces(
                    target.device_id,
                    DeviceObservation(
                        source="snmpv3",
                        observed_at=now,
                        hostname=snapshot.hostname,
                        interfaces=snapshot.interfaces,
                        interface_snapshot_complete=True,
                    ),
                )
                self._nms.append_interface_samples(target.device_id, now, snapshot.counters)
                self._nms.reconcile_neighbors(target.device_id, now, snapshot.neighbors)
                self._nms.replace_routes(target.device_id, now, snapshot.routes)
                self._nms.replace_arp(target.device_id, now, snapshot.arp_entries)
                self._nms.replace_vlans(target.device_id, now, snapshot.vlans)
                self._nms.mark_poll_result(target.id, now, None)
                succeeded += 1
            except (OSError, RuntimeError, ValueError):
                self._nms.mark_poll_result(target.id, now, "poll_failed")
                failed += 1
        return succeeded, failed


def _suffix_map(root: str, values: dict[str, str]) -> dict[str, str]:
    prefix = root + "."
    return {oid[len(prefix):]: value for oid, value in values.items() if oid.startswith(prefix)}


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _mac(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.replace(" ", ":").replace("-", ":").upper()
    if cleaned.startswith("0X"):
        raw = cleaned[2:]
        if len(raw) == 12:
            return ":".join(raw[i:i + 2] for i in range(0, 12, 2))
    return cleaned


def parse_snapshot(hostname: str | None, values: dict[str, dict[str, str]]) -> SnmpSnapshot:
    names = _suffix_map(_IF_NAME, values.get(_IF_NAME, {}))
    speed = _suffix_map(_IF_HIGH_SPEED, values.get(_IF_HIGH_SPEED, {}))
    mtu = _suffix_map(_IF_MTU, values.get(_IF_MTU, {}))
    phys = _suffix_map(_IF_PHYS, values.get(_IF_PHYS, {}))
    oper = _suffix_map(_IF_OPER, values.get(_IF_OPER, {}))
    in_octets = _suffix_map(_IF_HC_IN, values.get(_IF_HC_IN, {}))
    out_octets = _suffix_map(_IF_HC_OUT, values.get(_IF_HC_OUT, {}))
    in_errors = _suffix_map(_IF_IN_ERRORS, values.get(_IF_IN_ERRORS, {}))
    out_errors = _suffix_map(_IF_OUT_ERRORS, values.get(_IF_OUT_ERRORS, {}))

    interfaces: list[ObservedNetworkInterface] = []
    counters: list[dict[str, object]] = []
    index_to_name: dict[str, str] = {}
    for index, name in names.items():
        index_to_name[index] = name
        status = {"1": InterfaceOperationalStatus.UP, "2": InterfaceOperationalStatus.DOWN}.get(
            oper.get(index),
            InterfaceOperationalStatus.UNKNOWN,
        )
        speed_mbps = _as_int(speed.get(index))
        interfaces.append(
            ObservedNetworkInterface(
                name=name,
                mac_address=_mac(phys.get(index)),
                operational_status=status,
                mtu=_as_int(mtu.get(index)),
                speed_bps=speed_mbps * 1_000_000 if speed_mbps is not None else None,
            )
        )
        counters.append(
            {
                "interface_name": name,
                "in_octets": _as_int(in_octets.get(index)),
                "out_octets": _as_int(out_octets.get(index)),
                "in_errors": _as_int(in_errors.get(index)),
                "out_errors": _as_int(out_errors.get(index)),
            }
        )

    lldp_local = _suffix_map(_LLDP_REM_LOCAL_PORT, values.get(_LLDP_REM_LOCAL_PORT, {}))
    lldp_chassis = _suffix_map(_LLDP_REM_CHASSIS, values.get(_LLDP_REM_CHASSIS, {}))
    lldp_port = _suffix_map(_LLDP_REM_PORT, values.get(_LLDP_REM_PORT, {}))
    lldp_name = _suffix_map(_LLDP_REM_SYSNAME, values.get(_LLDP_REM_SYSNAME, {}))
    neighbors: list[dict[str, str | None]] = []
    for key, local_index in lldp_local.items():
        neighbors.append(
            {
                "local_interface": index_to_name.get(local_index, f"ifIndex:{local_index}"),
                "protocol": "lldp",
                "remote_chassis_id": _mac(lldp_chassis.get(key)) or lldp_chassis.get(key),
                "remote_system_name": lldp_name.get(key),
                "remote_port_id": lldp_port.get(key),
            }
        )

    cdp_devices = _suffix_map(_CDP_DEVICE_ID, values.get(_CDP_DEVICE_ID, {}))
    cdp_ports = _suffix_map(_CDP_DEVICE_PORT, values.get(_CDP_DEVICE_PORT, {}))
    for key, remote_name in cdp_devices.items():
        local_index = key.split(".", 1)[0]
        neighbors.append(
            {
                "local_interface": index_to_name.get(local_index, f"ifIndex:{local_index}"),
                "protocol": "cdp",
                "remote_chassis_id": None,
                "remote_system_name": remote_name,
                "remote_port_id": cdp_ports.get(key),
            }
        )

    destinations = _suffix_map(_ROUTE_DEST, values.get(_ROUTE_DEST, {}))
    masks = _suffix_map(_ROUTE_MASK, values.get(_ROUTE_MASK, {}))
    next_hops = _suffix_map(_ROUTE_NEXTHOP, values.get(_ROUTE_NEXTHOP, {}))
    route_if = _suffix_map(_ROUTE_IFINDEX, values.get(_ROUTE_IFINDEX, {}))
    route_type = _suffix_map(_ROUTE_TYPE, values.get(_ROUTE_TYPE, {}))
    routes: list[dict[str, object]] = []
    for key, destination in destinations.items():
        mask = masks.get(key, "255.255.255.255")
        try:
            prefix = IPv4Network(f"0.0.0.0/{mask}").prefixlen
        except ValueError:
            continue
        routes.append(
            {
                "destination": destination,
                "prefix_length": prefix,
                "next_hop": next_hops.get(key),
                "interface_name": index_to_name.get(route_if.get(key, "")),
                "route_type": route_type.get(key),
            }
        )

    arp_phys = _suffix_map(_ARP_PHYS, values.get(_ARP_PHYS, {}))
    arp_ip = _suffix_map(_ARP_IP, values.get(_ARP_IP, {}))
    arp_entries: list[dict[str, str | None]] = []
    for key, phys_address in arp_phys.items():
        if_index = key.split(".", 1)[0]
        ip_value = arp_ip.get(key)
        mac_address = _mac(phys_address)
        if ip_value and mac_address:
            arp_entries.append(
                {
                    "interface_name": index_to_name.get(if_index),
                    "ip_address": ip_value,
                    "mac_address": mac_address,
                }
            )

    vlan_names = _suffix_map(_VLAN_NAME, values.get(_VLAN_NAME, {}))
    vlans = [
        {"vlan_id": int(index), "name": name}
        for index, name in vlan_names.items()
        if index.isdigit() and 1 <= int(index) <= 4094
    ]
    return SnmpSnapshot(
        hostname=hostname,
        interfaces=tuple(interfaces),
        counters=counters,
        neighbors=neighbors,
        routes=routes,
        arp_entries=arp_entries,
        vlans=vlans,
    )
