from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat


class AlertRuleCreateRequest(BaseModel):
    metricName: str = Field(min_length=1, max_length=128)
    operator: Literal[">", ">=", "<", "<="]
    threshold: FiniteFloat
    durationSeconds: int = Field(default=0, ge=0, le=86400)


class AlertRuleResponse(BaseModel):
    id: int
    metricName: str
    operator: str
    threshold: float
    durationSeconds: int
    enabled: bool


class AlertPresetResponse(BaseModel):
    preset: str
    created: int
    rules: list[AlertRuleResponse]


class AlertResponse(BaseModel):
    id: int
    ruleId: int
    deviceId: str
    openedAt: datetime
    closedAt: datetime | None
    active: bool
    metricName: str
    operator: str
    threshold: float
    durationSeconds: int
    silenced: bool
    maintenanceWindowId: int | None
