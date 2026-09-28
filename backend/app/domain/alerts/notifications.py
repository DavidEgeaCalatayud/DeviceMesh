from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NotificationChannelKind(StrEnum):
    WEBHOOK = "webhook"
    SLACK = "slack"
    EMAIL = "email"


class NotificationTransitionFilter(StrEnum):
    OPENED = "opened"
    RECOVERED = "recovered"
    BOTH = "both"


class NotificationDeliveryStatus(StrEnum):
    QUEUED = "queued"
    DELIVERED = "delivered"
    DEAD = "dead"


@dataclass(frozen=True, slots=True)
class NotificationChannel:
    id: int
    name: str
    kind: NotificationChannelKind
    secret_ref: str
    config: dict[str, object]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class NotificationRoute:
    id: int
    name: str
    channel_id: int
    transition: NotificationTransitionFilter
    metric_name: str | None = None
    device_id: str | None = None
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class NotificationDelivery:
    id: int
    channel_id: int
    route_id: int
    alert_id: int
    transition: str
    payload: dict[str, object]
    status: NotificationDeliveryStatus
    attempts: int
    next_attempt_at: datetime
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None
