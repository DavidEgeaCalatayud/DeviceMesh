from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.network.models import ObservedService


class DeviceStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    hostname: str | None = None
    operating_system: str | None = None
    operating_system_version: str | None = None
    architecture: str | None = None
    manufacturer: str | None = None
    ip_addresses: tuple[str, ...] = ()
    mac_addresses: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeviceObservation:
    source: str
    observed_at: datetime
    hostname: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    manufacturer: str | None = None
    network_cidr: str | None = None
    services: tuple[ObservedService, ...] = ()
    service_snapshot_complete: bool = False
    scanned_tcp_ports: tuple[int, ...] = ()
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Device:
    id: str
    hostname: str | None = None
    ip_addresses: set[str] = field(default_factory=set)
    mac_addresses: set[str] = field(default_factory=set)
    operating_system: str | None = None
    operating_system_version: str | None = None
    architecture: str | None = None
    manufacturer: str | None = None
    status: DeviceStatus = DeviceStatus.UNKNOWN
    first_seen: datetime | None = None
    last_seen: datetime | None = None
