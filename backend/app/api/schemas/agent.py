from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    type: Literal["heartbeat"]
    protocolVersion: Literal[1]
    agentId: str = Field(min_length=1, max_length=128)
    timestamp: datetime


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
