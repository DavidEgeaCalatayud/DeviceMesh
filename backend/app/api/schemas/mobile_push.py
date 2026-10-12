from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MobilePushRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["fcm", "apns"]
    environment: Literal["production", "sandbox"] = "production"
    installationId: str = Field(min_length=8, max_length=128)
    token: str = Field(min_length=16, max_length=4096)


class MobilePushRegistrationResponse(BaseModel):
    id: str
    provider: str
    environment: str
    installationId: str
