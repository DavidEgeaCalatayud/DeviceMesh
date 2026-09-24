from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class SyntheticMonitorType(StrEnum):
    HTTP = "http"
    TCP = "tcp"
    ICMP = "icmp"


class SyntheticState(StrEnum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SyntheticMonitor:
    id: str
    device_id: str
    name: str
    monitor_type: SyntheticMonitorType
    target: str
    port: int | None
    expected_status_min: int | None
    expected_status_max: int | None
    interval_seconds: int
    timeout_seconds: int
    enabled: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SyntheticProbeResult:
    id: int
    monitor_id: str
    probe_id: str
    observed_at: datetime
    success: bool
    latency_ms: float | None = None
    http_status: int | None = None
    failure_reason: str | None = None
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SyntheticSlaWindow:
    label: str
    window_start: datetime
    window_end: datetime
    monitored_seconds: float
    up_seconds: float
    downtime_seconds: float
    availability_percent: float | None
    outage_count: int
    longest_outage_seconds: float
    latency_average_ms: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None


@dataclass(frozen=True, slots=True)
class SyntheticOutage:
    started_at: datetime
    ended_at: datetime | None
    active: bool
    duration_seconds: float
    last_failure_reason: str | None


@dataclass(frozen=True, slots=True)
class SyntheticHealthSummary:
    monitor: SyntheticMonitor
    generated_at: datetime
    current_state: SyntheticState
    current_outage_seconds: float
    stale: bool
    last_observed_at: datetime | None
    latest_latency_ms: float | None
    latest_http_status: int | None
    latest_failure_reason: str | None
    windows: tuple[SyntheticSlaWindow, ...]
