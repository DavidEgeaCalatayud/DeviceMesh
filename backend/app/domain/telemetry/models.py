from dataclasses import dataclass
from datetime import datetime


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
