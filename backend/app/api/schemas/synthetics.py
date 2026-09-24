from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SyntheticMonitorCreateRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    monitorType: Literal["http", "tcp", "icmp"]
    target: str = Field(min_length=1, max_length=2048)
    port: int | None = Field(default=None, ge=1, le=65535)
    expectedStatusMin: int | None = Field(default=None, ge=100, le=599)
    expectedStatusMax: int | None = Field(default=None, ge=100, le=599)
    intervalSeconds: int = Field(default=60, ge=15, le=3600)
    timeoutSeconds: int = Field(default=5, ge=1, le=30)


class SyntheticMonitorUpdateRequest(SyntheticMonitorCreateRequest):
    enabled: bool = True


class SyntheticMonitorResponse(BaseModel):
    id: str
    deviceId: str
    name: str
    monitorType: str
    target: str
    port: int | None
    expectedStatusMin: int | None
    expectedStatusMax: int | None
    intervalSeconds: int
    timeoutSeconds: int
    enabled: bool
    createdBy: str
    createdAt: datetime
    updatedAt: datetime


class SyntheticProbeObservationRequest(BaseModel):
    monitorId: str = Field(min_length=1, max_length=36)
    observedAt: datetime
    success: bool
    latencyMs: float | None = Field(default=None, ge=0)
    httpStatus: int | None = Field(default=None, ge=100, le=599)
    failureReason: str | None = Field(default=None, max_length=2048)
    attributes: dict[str, object] = Field(default_factory=dict)


class SyntheticProbeBatchRequest(BaseModel):
    probeId: str = Field(min_length=1, max_length=128)
    results: list[SyntheticProbeObservationRequest] = Field(max_length=1000)


class SyntheticProbeResultResponse(BaseModel):
    id: int
    monitorId: str
    probeId: str
    observedAt: datetime
    success: bool
    latencyMs: float | None
    httpStatus: int | None
    failureReason: str | None
    attributes: dict[str, object]


class SyntheticSlaWindowResponse(BaseModel):
    label: str
    windowStart: datetime
    windowEnd: datetime
    monitoredSeconds: float
    upSeconds: float
    downtimeSeconds: float
    availabilityPercent: float | None
    outageCount: int
    longestOutageSeconds: float
    latencyAverageMs: float | None
    latencyP50Ms: float | None
    latencyP95Ms: float | None


class SyntheticOutageResponse(BaseModel):
    startedAt: datetime
    endedAt: datetime | None
    active: bool
    durationSeconds: float
    lastFailureReason: str | None


class SyntheticHealthResponse(BaseModel):
    monitor: SyntheticMonitorResponse
    generatedAt: datetime
    currentState: Literal["up", "down", "unknown"]
    currentOutageSeconds: float
    stale: bool
    lastObservedAt: datetime | None
    latestLatencyMs: float | None
    latestHttpStatus: int | None
    latestFailureReason: str | None
    windows: list[SyntheticSlaWindowResponse]
    outages: list[SyntheticOutageResponse]
