from datetime import datetime

from app.application.ports import DeviceRepository
from app.domain.devices.models import Device


class RecordHeartbeat:
    def __init__(self, devices: DeviceRepository) -> None:
        self._devices = devices

    def execute(self, agent_id: str, timestamp: datetime) -> Device:
        return self._devices.mark_agent_online(agent_id, timestamp)
