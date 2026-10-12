from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NotificationChannelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["webhook", "slack", "email", "push"]
    secretRef: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    config: dict[str, object] = Field(default_factory=dict)


class NotificationChannelResponse(BaseModel):
    id: int
    name: str
    kind: str
    secretRef: str
    config: dict[str, object]
    enabled: bool


class NotificationRouteCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    channelId: int = Field(gt=0)
    transition: Literal["opened", "recovered", "both"] = "both"
    metricName: str | None = Field(default=None, min_length=1, max_length=128)
    deviceId: str | None = Field(default=None, min_length=1, max_length=128)


class NotificationRouteResponse(BaseModel):
    id: int
    name: str
    channelId: int
    transition: str
    metricName: str | None
    deviceId: str | None
    enabled: bool


class NotificationStateRequest(BaseModel):
    enabled: bool


class NotificationDeliveryResponse(BaseModel):
    id: int
    channelId: int
    routeId: int
    alertId: int
    transition: str
    status: str
    attempts: int
    nextAttemptAt: datetime
    lastAttemptAt: datetime | None
    deliveredAt: datetime | None
    lastError: str | None
    payload: dict[str, object]
