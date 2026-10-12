from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MetricSeriesPointResponse(BaseModel):
    timestamp: datetime
    value: float
    minimum: float
    maximum: float
    samples: int
    source: Literal["raw", "hourly_rollup"]


class MetricSeriesResponse(BaseModel):
    deviceId: str
    name: str
    unit: str | None
    start: datetime
    end: datetime
    bucketSeconds: int | None
    resolution: Literal["raw", "hourly"]
    truncated: bool
    points: list[MetricSeriesPointResponse]


class TelemetryCompactionResponse(BaseModel):
    cutoff: datetime
    rollupsTouched: int
    rawSamplesDeleted: int
    rawRetentionDays: int


class RetentionPolicyResponse(BaseModel):
    runIntervalSeconds: int
    telemetryRawDays: int
    telemetryHourlyDays: int
    deviceEventsDays: int
    syntheticChecksDays: int
    discoveryObservationsDays: int
    nmsInterfaceCountersDays: int
    syslogDays: int
    auditLogDays: int
    securityAuditDays: int
    notificationDeliveriesDays: int
    indefiniteClasses: list[str]


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
