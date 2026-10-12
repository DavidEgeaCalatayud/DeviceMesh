from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SnmpAuthProtocol(StrEnum):
    SHA256 = "sha256"


@dataclass(frozen=True, slots=True)
class NetworkManagementTarget:
    id: str
    device_id: str
    address: str
    port: int
    username: str
    auth_protocol: SnmpAuthProtocol
    auth_secret_ref: str
    interval_seconds: int
    enabled: bool
    last_polled_at: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class NetworkNeighbor:
    device_id: str
    local_interface: str
    protocol: str
    remote_chassis_id: str | None
    remote_system_name: str | None
    remote_port_id: str | None
    remote_device_id: str | None
    present: bool
    first_seen: datetime
    last_seen: datetime
    last_changed_at: datetime


@dataclass(frozen=True, slots=True)
class NetworkRoute:
    device_id: str
    destination: str
    prefix_length: int
    next_hop: str | None
    interface_name: str | None
    route_type: str | None
    source: str
    present: bool
    first_seen: datetime
    last_seen: datetime


@dataclass(frozen=True, slots=True)
class ArpEntry:
    device_id: str
    interface_name: str | None
    ip_address: str
    mac_address: str
    source: str
    present: bool
    first_seen: datetime
    last_seen: datetime


@dataclass(frozen=True, slots=True)
class VlanInventory:
    device_id: str
    vlan_id: int
    name: str | None
    source: str
    present: bool
    first_seen: datetime
    last_seen: datetime


@dataclass(frozen=True, slots=True)
class InterfaceCounterSample:
    device_id: str
    interface_name: str
    sampled_at: datetime
    in_octets: int | None
    out_octets: int | None
    in_errors: int | None
    out_errors: int | None
