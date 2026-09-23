from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RemoteOperationCreateRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    operationType: Literal[
        "telemetry.collect",
        "inventory.refresh",
        "agent.health_check",
    ]
    arguments: dict[str, object] = Field(default_factory=dict)
    ttlSeconds: int = Field(default=300, ge=30, le=3600)


class RemoteOperationResponse(BaseModel):
    id: str
    deviceId: str
    agentId: str
    operationType: str
    status: str
    requestedBy: str
    createdAt: datetime
    expiresAt: datetime
    arguments: dict[str, object]
    claimedAt: datetime | None
    completedAt: datetime | None
    result: dict[str, object]
    error: str | None


class RemoteOperationClaimResponse(BaseModel):
    id: str
    operationType: str
    arguments: dict[str, object]
    expiresAt: datetime


class RemoteOperationCompleteRequest(BaseModel):
    status: Literal["succeeded", "failed"]
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=1024)
