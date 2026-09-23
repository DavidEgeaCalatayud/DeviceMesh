from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ObservedServicePayload(BaseModel):
    port: int = Field(ge=1, le=65535)
    transport: str = Field(default="tcp", pattern="^tcp$")
    name: str | None = Field(default=None, max_length=128)


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
    attributes: dict[str, object] = Field(default_factory=dict)

    @field_validator("scannedTcpPorts")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("scanned TCP ports must be between 1 and 65535")
        return sorted(set(ports))


class DiscoveryBatchRequest(BaseModel):
    observations: list[DiscoveryObservationPayload] = Field(min_length=1, max_length=4096)
