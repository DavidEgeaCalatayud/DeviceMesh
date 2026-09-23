from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


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
