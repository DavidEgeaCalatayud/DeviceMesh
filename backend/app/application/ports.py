from datetime import datetime
from typing import Protocol

from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation
from app.domain.telemetry.models import TelemetryBatch


class DeviceRepository(Protocol):
    def list_devices(self) -> list[Device]: ...

    def mark_agent_online(
        self,
        agent_id: str,
        timestamp: datetime,
        identity: DeviceIdentity | None = None,
    ) -> Device: ...

    def record_observation(self, observation: DeviceObservation) -> Device: ...


class TelemetryRepository(Protocol):
    def append(self, batch: TelemetryBatch) -> None: ...
