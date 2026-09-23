from datetime import datetime

from app.application.ports import DeviceRepository, EventRepository
from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation, DeviceStatus
from app.domain.events.models import DeviceEvent


class EventRecordingDeviceRepository:
    def __init__(self, devices: DeviceRepository, events: EventRepository) -> None:
        self._devices = devices
        self._events = events

    def list_devices(self) -> list[Device]:
        return self._devices.list_devices()

    def mark_agent_online(
        self,
        agent_id: str,
        timestamp: datetime,
        identity: DeviceIdentity | None = None,
    ) -> Device:
        before = next((device for device in self._devices.list_devices() if device.id == agent_id), None)
        previous_ips = set(before.ip_addresses) if before is not None else set()
        previous_status = before.status if before is not None else DeviceStatus.UNKNOWN
        device = self._devices.mark_agent_online(agent_id, timestamp, identity)

        if before is None:
            self._events.append(
                DeviceEvent(
                    device_id=device.id,
                    name="AGENT_CONNECTED",
                    timestamp=timestamp,
                    attributes={"hostname": device.hostname or device.id},
                )
            )
        elif previous_status is not DeviceStatus.ONLINE:
            self._events.append(
                DeviceEvent(device_id=device.id, name="DEVICE_ONLINE", timestamp=timestamp)
            )

        self._record_ip_change(device, previous_ips, timestamp, "agent")
        return device

    def record_observation(self, observation: DeviceObservation) -> Device:
        before = self._match_observation(observation)
        previous_ips = set(before.ip_addresses) if before is not None else set()
        device = self._devices.record_observation(observation)

        if before is None:
            self._events.append(
                DeviceEvent(
                    device_id=device.id,
                    name="DEVICE_DISCOVERED",
                    timestamp=observation.observed_at,
                    attributes={
                        "source": observation.source,
                        "hostname": device.hostname or device.id,
                        "ipAddress": observation.ip_address,
                        "macAddress": observation.mac_address,
                    },
                )
            )
        else:
            self._record_ip_change(
                device,
                previous_ips,
                observation.observed_at,
                observation.source,
            )
        return device

    def _match_observation(self, observation: DeviceObservation) -> Device | None:
        devices = self._devices.list_devices()
        if observation.mac_address:
            mac = observation.mac_address.upper().replace("-", ":")
            match = next((device for device in devices if mac in device.mac_addresses), None)
            if match is not None:
                return match
        if observation.hostname:
            match = next(
                (device for device in devices if device.hostname == observation.hostname),
                None,
            )
            if match is not None:
                return match
        if observation.ip_address:
            return next(
                (
                    device
                    for device in devices
                    if observation.ip_address in device.ip_addresses
                ),
                None,
            )
        return None

    def _record_ip_change(
        self,
        device: Device,
        previous_ips: set[str],
        timestamp: datetime,
        source: str,
    ) -> None:
        if not previous_ips or device.ip_addresses == previous_ips:
            return
        added = sorted(device.ip_addresses - previous_ips)
        removed = sorted(previous_ips - device.ip_addresses)
        if not added and not removed:
            return
        self._events.append(
            DeviceEvent(
                device_id=device.id,
                name="IP_CHANGED",
                timestamp=timestamp,
                attributes={"source": source, "added": added, "removed": removed},
            )
        )
