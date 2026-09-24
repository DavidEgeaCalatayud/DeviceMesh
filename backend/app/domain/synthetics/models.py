from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SyntheticMonitorKind(StrEnum):
    HTTP = "http"
    TCP = "tcp"
    ICMP = "icmp"


class SyntheticCheckErrorKind(StrEnum):
    DNS = "dns"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    HTTP_STATUS = "http_status"
    POLICY = "policy"
    UNSUPPORTED = "unsupported"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class SyntheticMonitor:
    id: str
    name: str
    kind: SyntheticMonitorKind
    target: str
    port: int | None
    device_id: str | None
    interval_seconds: int
    timeout_seconds: float
    enabled: bool
    http_method: str | None
    expected_status: int | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime


@dataclass(frozen=True, slots=True)
class SyntheticCheckResult:
    id: int
    monitor_id: str
    checked_at: datetime
    success: bool
    latency_ms: float
    http_status: int | None
    error_kind: SyntheticCheckErrorKind | None
    error: str | None
    probe_id: str


@dataclass(frozen=True, slots=True)
class SyntheticSlaWindow:
    label: str
    window_start: datetime
    window_end: datetime
    total_checks: int
    successful_checks: int
    failed_checks: int
    availability_percent: float | None
    mean_latency_ms: float | None
    p95_latency_ms: float | None


@dataclass(frozen=True, slots=True)
class SyntheticHealthSummary:
    monitor_id: str
    generated_at: datetime
    consecutive_failures: int
    failing_since: datetime | None
    windows: tuple[SyntheticSlaWindow, ...]
