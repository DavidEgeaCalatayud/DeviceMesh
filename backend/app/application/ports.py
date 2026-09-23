from datetime import datetime
from typing import Protocol

from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation
from app.domain.events.models import DeviceEvent
from app.domain.telemetry.models import MetricSample, TelemetryBatch


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

    def list_latest(self) -> list[MetricSample]: ...


class EventRepository(Protocol):
    def append(self, event: DeviceEvent) -> None: ...

    def list_recent(self, limit: int = 100) -> list[DeviceEvent]: ...
