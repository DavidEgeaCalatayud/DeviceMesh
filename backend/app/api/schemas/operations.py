from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RemoteOperationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deviceId: str = Field(min_length=1, max_length=128)
    operationType: Literal[
        "telemetry.collect",
        "inventory.refresh",
        "agent.health_check",
        "network.dns_lookup",
        "network.route_snapshot",
        "firmware.update",
    ]
    arguments: dict[str, object] = Field(default_factory=dict)
    ttlSeconds: int = Field(default=300, ge=30, le=3600)

    @model_validator(mode="after")
    def validate_operation_arguments(self) -> "RemoteOperationCreateRequest":
        if self.operationType == "network.dns_lookup":
            if set(self.arguments) != {"hostname"}:
                raise ValueError("network.dns_lookup requires only the hostname argument")
            hostname = self.arguments.get("hostname")
            if not isinstance(hostname, str) or not 1 <= len(hostname.strip()) <= 253:
                raise ValueError("hostname must be a non-empty string of at most 253 characters")
        elif self.operationType == "firmware.update":
            if set(self.arguments) != {"url", "sha256", "version"}:
                raise ValueError(
                    "firmware.update requires only url, sha256 and version arguments"
                )
            url = self.arguments.get("url")
            sha256 = self.arguments.get("sha256")
            version = self.arguments.get("version")
            if (
                not isinstance(url, str)
                or not url.startswith("https://")
                or not 12 <= len(url) <= 2048
            ):
                raise ValueError("firmware update URL must be a bounded HTTPS URL")
            if (
                not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdefABCDEF" for character in sha256)
            ):
                raise ValueError("firmware update sha256 must be 64 hexadecimal characters")
            if not isinstance(version, str) or not 1 <= len(version.strip()) <= 64:
                raise ValueError("firmware update version must be 1-64 characters")
        elif self.arguments:
            raise ValueError(f"{self.operationType} does not accept arguments")
        return self


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
    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    result: dict[str, object] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=1024)
