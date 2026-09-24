from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SyntheticProbeObservation:
    monitor_id: str
    observed_at: datetime
    success: bool
    latency_ms: float | None = None
    http_status: int | None = None
    failure_reason: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)
