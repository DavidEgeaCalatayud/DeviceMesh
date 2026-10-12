from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RemoteOperationType(StrEnum):
    TELEMETRY_COLLECT = "telemetry.collect"
    INVENTORY_REFRESH = "inventory.refresh"
    AGENT_HEALTH_CHECK = "agent.health_check"
    NETWORK_DNS_LOOKUP = "network.dns_lookup"
    NETWORK_ROUTE_SNAPSHOT = "network.route_snapshot"
    FIRMWARE_UPDATE = "firmware.update"


class RemoteOperationStatus(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class RemoteOperation:
    id: str
    device_id: str
    agent_id: str
    operation_type: RemoteOperationType
    status: RemoteOperationStatus
    requested_by: str
    created_at: datetime
    expires_at: datetime
    arguments: dict[str, object] = field(default_factory=dict)
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, object] = field(default_factory=dict)
    error: str | None = None
