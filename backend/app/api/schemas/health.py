from datetime import datetime

from pydantic import BaseModel, Field


class SlaWindowResponse(BaseModel):
    label: str
    windowStart: datetime
    windowEnd: datetime
    monitoredSeconds: float
    onlineSeconds: float
    downtimeSeconds: float
    availabilityPercent: float | None
    outageCount: int
    longestOutageSeconds: float
    meanRecoverySeconds: float | None


class DeviceHealthResponse(BaseModel):
    deviceId: str
    generatedAt: datetime
    currentState: str | None
    currentOutageSeconds: float
    maintenanceActive: bool
    maintenanceWindowId: int | None
    windows: list[SlaWindowResponse]


class OutageResponse(BaseModel):
    id: int
    deviceId: str
    startedAt: datetime
    endedAt: datetime | None
    durationSeconds: float
    active: bool
    source: str


class MaintenanceWindowCreateRequest(BaseModel):
    deviceId: str | None = Field(default=None, min_length=1, max_length=128)
    startsAt: datetime
    endsAt: datetime
    reason: str = Field(min_length=1, max_length=512)


class MaintenanceWindowResponse(BaseModel):
    id: int
    deviceId: str | None
    startsAt: datetime
    endsAt: datetime
    reason: str
    createdBy: str
    createdAt: datetime
    cancelledAt: datetime | None
    active: bool
