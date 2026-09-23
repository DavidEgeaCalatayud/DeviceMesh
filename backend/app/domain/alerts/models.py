from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    metric_name: str
    operator: str
    threshold: float
    duration_seconds: int = 0

    def matches(self, value: float) -> bool:
        operations = {
            ">": lambda: value > self.threshold,
            ">=": lambda: value >= self.threshold,
            "<": lambda: value < self.threshold,
            "<=": lambda: value <= self.threshold,
        }
        try:
            return operations[self.operator]()
        except KeyError as exc:
            raise ValueError(f"unsupported operator: {self.operator}") from exc


@dataclass(frozen=True, slots=True)
class AlertRule:
    id: int
    condition: ThresholdRule
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AlertIncident:
    id: int
    rule_id: int
    device_id: str
    opened_at: datetime
    closed_at: datetime | None = None


class AlertTransitionType(StrEnum):
    OPENED = "opened"
    RECOVERED = "recovered"


@dataclass(frozen=True, slots=True)
class AlertTransition:
    type: AlertTransitionType
    incident: AlertIncident
    rule: AlertRule
    value: float
    timestamp: datetime
