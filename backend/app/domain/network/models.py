from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ServiceState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class InterfaceOperationalStatus(StrEnum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObservedService:
    port: int
    transport: str = "tcp"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ObservedNetworkInterface:
    name: str
    mac_address: str | None = None
    operational_status: InterfaceOperationalStatus = InterfaceOperationalStatus.UNKNOWN
    mtu: int | None = None
    speed_bps: int | None = None
    vlan_id: int | None = None
    ip_addresses: tuple[str, ...] = ()
    gateways: tuple[str, ...] = ()
    dns_servers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NetworkInterfaceInventory:
    device_id: str
    name: str
    mac_address: str | None
    operational_status: InterfaceOperationalStatus
    mtu: int | None
    speed_bps: int | None
    vlan_id: int | None
    ip_addresses: tuple[str, ...]
    gateways: tuple[str, ...]
    dns_servers: tuple[str, ...]
    source: str
    present: bool
    first_seen: datetime
    last_seen: datetime
    last_changed_at: datetime


@dataclass(frozen=True, slots=True)
class DeviceService:
    device_id: str
    port: int
    transport: str
    name: str | None
    state: ServiceState
    first_seen: datetime
    last_seen: datetime
    last_changed_at: datetime
    source: str
    network_cidr: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceTransition:
    name: str
    service: DeviceService


@dataclass(frozen=True, slots=True)
class TopologyNode:
    id: str
    kind: str
    label: str
    device_id: str | None = None
    network_cidr: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class TopologyEdge:
    source: str
    target: str
    relation: str = "observed-on"


@dataclass(frozen=True, slots=True)
class NetworkTopology:
    nodes: tuple[TopologyNode, ...]
    edges: tuple[TopologyEdge, ...]
    method: str = "observation-segment"
    approximate: bool = True
