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
    failureThreshold: int = Field(default=3, ge=1, le=20)
    recoveryThreshold: int = Field(default=2, ge=1, le=20)


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
    failureThreshold: int
    recoveryThreshold: int
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
    probeLocation: str | None
    workId: str | None


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


class SyntheticProbeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    location: str = Field(min_length=1, max_length=128)
    capabilities: list[Literal["http", "tcp", "icmp"]] = Field(min_length=1, max_length=3)


class SyntheticProbeResponse(BaseModel):
    id: str
    name: str
    location: str
    capabilities: list[str]
    enabled: bool
    lastSeenAt: datetime | None
    online: bool
    createdAt: datetime
    updatedAt: datetime


class SyntheticProbeRegistrationResponse(BaseModel):
    probe: SyntheticProbeResponse
    token: str


class SyntheticProbeStateRequest(BaseModel):
    enabled: bool


class SyntheticProbeAssignmentResponse(BaseModel):
    monitorId: str
    probeId: str
    enabled: bool
    nextRunAt: datetime
    createdAt: datetime
    updatedAt: datetime


class SyntheticProbeAssignmentStateRequest(BaseModel):
    enabled: bool


class SyntheticProbeHeartbeatResponse(BaseModel):
    probeId: str
    lastSeenAt: datetime


class SyntheticWorkMonitorResponse(BaseModel):
    id: str
    name: str
    kind: str
    target: str
    port: int | None
    timeoutSeconds: float
    httpMethod: str | None
    expectedStatus: int | None


class SyntheticWorkResponse(BaseModel):
    workId: str
    assignedAt: datetime
    leaseExpiresAt: datetime
    monitor: SyntheticWorkMonitorResponse


class SyntheticWorkResultRequest(BaseModel):
    workId: str = Field(min_length=36, max_length=36)
    checkedAt: datetime
    success: bool
    latencyMs: float = Field(ge=0.0, le=3600000.0)
    httpStatus: int | None = Field(default=None, ge=100, le=599)
    errorKind: Literal[
        "dns",
        "timeout",
        "connection",
        "http_status",
        "policy",
        "unsupported",
        "internal",
    ] | None = None
    error: str | None = Field(default=None, max_length=1024)


class ProbeServiceStateResponse(BaseModel):
    probeId: str
    location: str
    success: bool
    checkedAt: datetime
    latencyMs: float


class ServiceConsensusResponse(BaseModel):
    monitorId: str
    generatedAt: datetime
    classification: str
    healthyProbes: int
    failingProbes: int
    states: list[ProbeServiceStateResponse]


class ServiceIncidentResponse(BaseModel):
    id: str
    monitorId: str
    state: str
    classification: str
    openedAt: datetime
    resolvedAt: datetime | None
    lastObservedAt: datetime
    durationSeconds: float
    failureThreshold: int
    recoveryThreshold: int
    maintenanceActiveAtOpen: bool
    hostOfflineAtOpen: bool
    failingProbes: int
    totalProbes: int


class ServiceIncidentSummaryResponse(BaseModel):
    monitorId: str
    openIncident: ServiceIncidentResponse | None
    incidents: list[ServiceIncidentResponse]
    resolvedCount: int
    meanRecoverySeconds: float | None
