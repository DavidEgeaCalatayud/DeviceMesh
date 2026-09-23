from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class EventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class DeviceEvent:
    device_id: str
    name: str
    timestamp: datetime
    severity: EventSeverity = EventSeverity.INFO
    attributes: dict[str, object] = field(default_factory=dict)
