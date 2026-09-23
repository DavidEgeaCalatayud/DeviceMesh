from datetime import datetime

from pydantic import BaseModel


class MetricSeriesPointResponse(BaseModel):
    timestamp: datetime
    value: float
    minimum: float
    maximum: float
    samples: int


class MetricSeriesResponse(BaseModel):
    deviceId: str
    name: str
    unit: str | None
    start: datetime
    end: datetime
    bucketSeconds: int | None
    truncated: bool
    points: list[MetricSeriesPointResponse]


class DiagnosticSignalResponse(BaseModel):
    name: str
    latest: float
    average: float
    unit: str | None
    samples: int


class NetworkDiagnosticResponse(BaseModel):
    deviceId: str
    state: str
    coverage: str
    windowStart: datetime
    windowEnd: datetime
    method: str
    approximate: bool
    signals: list[DiagnosticSignalResponse]
    reasons: list[str]
