from datetime import datetime

from pydantic import BaseModel, Field


class EnrollmentTokenCreateRequest(BaseModel):
    ttlSeconds: int | None = Field(default=None, ge=60, le=3600)


class EnrollmentTokenResponse(BaseModel):
    token: str
    expiresAt: datetime


class AgentEnrollmentRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    agentId: str = Field(min_length=1, max_length=128)


class AgentCredentialResponse(BaseModel):
    agentId: str
    credentialId: str
    credential: str
