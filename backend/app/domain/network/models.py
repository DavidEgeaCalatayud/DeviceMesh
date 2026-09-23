from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ServiceState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class ObservedService:
    port: int
    transport: str = "tcp"
    name: str | None = None


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
