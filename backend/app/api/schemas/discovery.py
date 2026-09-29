from datetime import datetime
from ipaddress import ip_address
import re

from pydantic import BaseModel, Field, field_validator

_MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class ObservedServicePayload(BaseModel):
    port: int = Field(ge=1, le=65535)
    transport: str = Field(default="tcp", pattern="^tcp$")
    name: str | None = Field(default=None, max_length=128)


class ObservedNetworkInterfacePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    macAddress: str | None = Field(default=None, max_length=64)
    operationalStatus: str = Field(default="unknown", pattern="^(up|down|unknown)$")
    mtu: int | None = Field(default=None, ge=68, le=1_000_000)
    speedBps: int | None = Field(default=None, ge=0, le=1_000_000_000_000_000)
    vlanId: int | None = Field(default=None, ge=1, le=4094)
    ipAddresses: list[str] = Field(default_factory=list, max_length=32)
    gateways: list[str] = Field(default_factory=list, max_length=16)
    dnsServers: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("macAddress")
    @classmethod
    def validate_mac(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _MAC_RE.fullmatch(value):
            raise ValueError("interface MAC address must contain six hexadecimal octets")
        return value.upper().replace("-", ":")

    @field_validator("ipAddresses", "gateways", "dnsServers")
    @classmethod
    def validate_ip_list(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            normalized.append(str(ip_address(value.strip())))
        return sorted(set(normalized))


class DiscoveryObservationPayload(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    observedAt: datetime
    hostname: str | None = Field(default=None, max_length=255)
    ipAddress: str | None = Field(default=None, max_length=64)
    macAddress: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=255)
    networkCidr: str | None = Field(default=None, max_length=64)
    services: list[ObservedServicePayload] = Field(default_factory=list, max_length=64)
    serviceSnapshotComplete: bool = False
    scannedTcpPorts: list[int] = Field(default_factory=list, max_length=64)
    interfaces: list[ObservedNetworkInterfacePayload] = Field(default_factory=list, max_length=128)
    interfaceSnapshotComplete: bool = False
    attributes: dict[str, object] = Field(default_factory=dict)

    @field_validator("scannedTcpPorts")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("scanned TCP ports must be between 1 and 65535")
        return sorted(set(ports))


class DiscoveryBatchRequest(BaseModel):
    observations: list[DiscoveryObservationPayload] = Field(min_length=1, max_length=4096)
