from datetime import datetime
from typing import Protocol

from app.domain.devices.models import Device
from app.domain.telemetry.models import TelemetryBatch


class DeviceRepository(Protocol):
    def list_devices(self) -> list[Device]: ...
    def mark_agent_online(self, agent_id: str, timestamp: datetime) -> Device: ...


class TelemetryRepository(Protocol):
    def append(self, batch: TelemetryBatch) -> None: ...
