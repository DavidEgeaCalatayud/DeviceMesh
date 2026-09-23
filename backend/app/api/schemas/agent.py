from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeviceIdentityPayload(BaseModel):
    hostname: str | None = Field(default=None, max_length=255)
    operatingSystem: str | None = Field(default=None, max_length=255)
    operatingSystemVersion: str | None = Field(default=None, max_length=255)
    architecture: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=255)
    ipAddresses: list[str] = Field(default_factory=list, max_length=64)
    macAddresses: list[str] = Field(default_factory=list, max_length=64)


class HeartbeatRequest(BaseModel):
    type: Literal["heartbeat"]
    protocolVersion: Literal[1]
    agentId: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    device: DeviceIdentityPayload | None = None


class MetricPayload(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    value: float
    unit: str | None = Field(default=None, max_length=32)


class TelemetryRequest(BaseModel):
    type: Literal["telemetry"]
    protocolVersion: Literal[1]
    agentId: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    metrics: list[MetricPayload] = Field(max_length=256)
