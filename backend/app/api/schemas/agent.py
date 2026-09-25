from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeviceIdentityPayload(StrictProtocolModel):
    hostname: str | None = Field(default=None, max_length=255)
    operatingSystem: str | None = Field(default=None, max_length=255)
    operatingSystemVersion: str | None = Field(default=None, max_length=255)
    architecture: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=255)
    ipAddresses: list[str] = Field(default_factory=list, max_length=64)
    macAddresses: list[str] = Field(default_factory=list, max_length=64)


class HeartbeatRequest(StrictProtocolModel):
    type: Literal["heartbeat"]
    protocolVersion: Literal[1]
    agentId: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    device: DeviceIdentityPayload | None = None


class MetricPayload(StrictProtocolModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    value: float = Field(allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=32)


class TelemetryRequest(StrictProtocolModel):
    type: Literal["telemetry"]
    protocolVersion: Literal[1]
    agentId: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    metrics: list[MetricPayload] = Field(max_length=256)
