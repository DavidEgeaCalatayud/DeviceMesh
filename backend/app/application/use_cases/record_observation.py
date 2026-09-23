from app.application.ports import DeviceRepository, EventRepository, NetworkRepository
from app.domain.devices.models import Device, DeviceObservation
from app.domain.events.models import DeviceEvent, EventSeverity


class RecordObservation:
    def __init__(
        self,
        devices: DeviceRepository,
        network: NetworkRepository | None = None,
        events: EventRepository | None = None,
    ) -> None:
        self._devices = devices
        self._network = network
        self._events = events

    def execute(self, observation: DeviceObservation) -> Device:
        device = self._devices.record_observation(observation)
        if self._network is None:
            return device

        transitions = self._network.reconcile_services(device.id, observation)
        if self._events is None:
            return device

        for transition in transitions:
            service = transition.service
            self._events.append(
                DeviceEvent(
                    device_id=device.id,
                    name=transition.name,
                    timestamp=service.last_changed_at,
                    severity=EventSeverity.INFO,
                    attributes={
                        "port": service.port,
                        "transport": service.transport,
                        "serviceName": service.name,
                        "networkCidr": service.network_cidr,
                    },
                )
            )
        return device
