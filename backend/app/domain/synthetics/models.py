from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SyntheticMonitorKind(StrEnum):
    HTTP = "http"
    TCP = "tcp"
    DNS = "dns"
    TLS = "tls"
    ICMP = "icmp"


class SyntheticCheckErrorKind(StrEnum):
    DNS = "dns"
    TLS = "tls"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    HTTP_STATUS = "http_status"
    POLICY = "policy"
    UNSUPPORTED = "unsupported"
    INTERNAL = "internal"


class ServiceConsensusClassification(StrEnum):
    HEALTHY = "healthy"
    GLOBAL_OUTAGE = "global_outage"
    REGIONAL_DEGRADATION = "regional_degradation"
    INSUFFICIENT_DATA = "insufficient_data"


class ServiceIncidentClassification(StrEnum):
    SERVICE_OUTAGE = "service_outage"
    REGIONAL_PATH = "regional_path"


class ServiceIncidentState(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


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
    failure_threshold: int
    recovery_threshold: int
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
    probe_location: str | None = None
    work_id: str | None = None


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


@dataclass(frozen=True, slots=True)
class SyntheticProbe:
    id: str
    name: str
    location: str
    capabilities: tuple[SyntheticMonitorKind, ...]
    enabled: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SyntheticProbeRegistration:
    probe: SyntheticProbe
    token: str


@dataclass(frozen=True, slots=True)
class SyntheticProbeAssignment:
    monitor_id: str
    probe_id: str
    enabled: bool
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SyntheticWorkItem:
    id: str
    probe_id: str
    monitor: SyntheticMonitor
    assigned_at: datetime
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProbeServiceState:
    probe_id: str
    location: str
    success: bool
    checked_at: datetime
    latency_ms: float
