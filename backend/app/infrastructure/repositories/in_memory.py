from datetime import datetime

from app.domain.devices.models import Device, DeviceStatus
from app.domain.telemetry.models import TelemetryBatch


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def list_devices(self) -> list[Device]:
        return list(self._devices.values())

    def mark_agent_online(self, agent_id: str, timestamp: datetime) -> Device:
        device = self._devices.setdefault(agent_id, Device(id=agent_id, first_seen=timestamp))
        device.status = DeviceStatus.ONLINE
        device.last_seen = timestamp
        return device


class InMemoryTelemetryRepository:
    def __init__(self) -> None:
        self.batches: list[TelemetryBatch] = []

    def append(self, batch: TelemetryBatch) -> None:
        self.batches.append(batch)
