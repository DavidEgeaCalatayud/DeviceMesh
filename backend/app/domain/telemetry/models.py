from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class Metric:
    name: str
    value: float
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class TelemetryBatch:
    agent_id: str
    timestamp: datetime
    metrics: tuple[Metric, ...]


@dataclass(frozen=True, slots=True)
class MetricSample:
    device_id: str
    timestamp: datetime
    metric: Metric


@dataclass(frozen=True, slots=True)
class MetricSeriesPoint:
    timestamp: datetime
    value: float
    minimum: float
    maximum: float
    samples: int


@dataclass(frozen=True, slots=True)
class MetricSeries:
    device_id: str
    metric_name: str
    unit: str | None
    start: datetime
    end: datetime
    bucket_seconds: int | None
    points: tuple[MetricSeriesPoint, ...]
    truncated: bool = False


class DiagnosticState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    POOR = "poor"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DiagnosticSignal:
    metric_name: str
    latest: float
    average: float
    unit: str | None
    sample_count: int


@dataclass(frozen=True, slots=True)
class NetworkDiagnostic:
    device_id: str
    state: DiagnosticState
    coverage: str
    window_start: datetime
    window_end: datetime
    signals: tuple[DiagnosticSignal, ...]
    reasons: tuple[str, ...]
    method: str = "threshold-heuristic-v1"
    approximate: bool = True
