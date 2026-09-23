from datetime import datetime

from pydantic import BaseModel, Field


class DiscoveryObservationPayload(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    observedAt: datetime
    hostname: str | None = Field(default=None, max_length=255)
    ipAddress: str | None = Field(default=None, max_length=64)
    macAddress: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=255)
    attributes: dict[str, object] = Field(default_factory=dict)


class DiscoveryBatchRequest(BaseModel):
    observations: list[DiscoveryObservationPayload] = Field(min_length=1, max_length=4096)
