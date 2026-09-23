from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AvailabilityState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class AvailabilityInterval:
    id: int
    device_id: str
    state: AvailabilityState
    started_at: datetime
    ended_at: datetime | None
    source: str

    def duration_seconds(self, now: datetime) -> float:
        end = self.ended_at or now
        return max(0.0, (end - self.started_at).total_seconds())


@dataclass(frozen=True, slots=True)
class SlaWindowSummary:
    label: str
    window_start: datetime
    window_end: datetime
    monitored_seconds: float
    online_seconds: float
    downtime_seconds: float
    availability_percent: float | None
    outage_count: int
    longest_outage_seconds: float
    mean_recovery_seconds: float | None


@dataclass(frozen=True, slots=True)
class DeviceHealthSummary:
    device_id: str
    generated_at: datetime
    current_state: AvailabilityState | None
    current_outage_seconds: float
    windows: tuple[SlaWindowSummary, ...]


@dataclass(frozen=True, slots=True)
class MaintenanceWindow:
    id: int
    device_id: str | None
    starts_at: datetime
    ends_at: datetime
    reason: str
    created_by: str
    created_at: datetime
    cancelled_at: datetime | None = None

    def is_active(self, timestamp: datetime) -> bool:
        return self.cancelled_at is None and self.starts_at <= timestamp < self.ends_at
