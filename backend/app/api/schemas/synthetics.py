from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SyntheticMonitorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: Literal["http", "tcp", "icmp"]
    target: str = Field(min_length=1, max_length=2048)
    port: int | None = Field(default=None, ge=1, le=65535)
    deviceId: str | None = Field(default=None, max_length=128)
    intervalSeconds: int = Field(default=60, ge=30, le=86400)
    timeoutSeconds: float = Field(default=5.0, ge=0.5, le=30.0)
    httpMethod: Literal["GET", "HEAD"] | None = None
    expectedStatus: int | None = Field(default=None, ge=100, le=599)


class SyntheticMonitorResponse(BaseModel):
    id: str
    name: str
    kind: str
    target: str
    port: int | None
    deviceId: str | None
    intervalSeconds: int
    timeoutSeconds: float
    enabled: bool
    httpMethod: str | None
    expectedStatus: int | None
    createdBy: str
    createdAt: datetime
    updatedAt: datetime
    nextRunAt: datetime


class SyntheticMonitorStateRequest(BaseModel):
    enabled: bool


class SyntheticCheckResponse(BaseModel):
    id: int
    monitorId: str
    checkedAt: datetime
    success: bool
    latencyMs: float
    httpStatus: int | None
    errorKind: str | None
    error: str | None
    probeId: str


class SyntheticSlaWindowResponse(BaseModel):
    label: str
    windowStart: datetime
    windowEnd: datetime
    totalChecks: int
    successfulChecks: int
    failedChecks: int
    availabilityPercent: float | None
    meanLatencyMs: float | None
    p95LatencyMs: float | None


class SyntheticHealthResponse(BaseModel):
    monitorId: str
    generatedAt: datetime
    consecutiveFailures: int
    failingSince: datetime | None
    windows: list[SyntheticSlaWindowResponse]
