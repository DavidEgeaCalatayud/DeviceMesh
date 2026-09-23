from app.application.ports import DeviceRepository
from app.domain.devices.models import Device, DeviceObservation


class RecordObservation:
    def __init__(self, devices: DeviceRepository) -> None:
        self._devices = devices

    def execute(self, observation: DeviceObservation) -> Device:
        return self._devices.record_observation(observation)
