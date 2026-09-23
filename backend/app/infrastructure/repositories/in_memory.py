from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation, DeviceStatus
from app.domain.telemetry.models import MetricSample, TelemetryBatch


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}

    def list_devices(self) -> list[Device]:
        return list(self._devices.values())

    def mark_agent_online(
        self,
        agent_id: str,
        timestamp: datetime,
        identity: DeviceIdentity | None = None,
    ) -> Device:
        device = self._devices.setdefault(agent_id, Device(id=agent_id, first_seen=timestamp))
        device.status = DeviceStatus.ONLINE
        device.last_seen = timestamp
        if identity is not None:
            device.hostname = identity.hostname or device.hostname
            device.operating_system = identity.operating_system or device.operating_system
            device.operating_system_version = (
                identity.operating_system_version or device.operating_system_version
            )
            device.architecture = identity.architecture or device.architecture
            device.manufacturer = identity.manufacturer or device.manufacturer
            device.ip_addresses.update(identity.ip_addresses)
            device.mac_addresses.update(identity.mac_addresses)
        return device

    def record_observation(self, observation: DeviceObservation) -> Device:
        device = self._find_observed_device(observation)
        if device is None:
            key = observation.mac_address or observation.hostname or observation.ip_address
            stable_key = key or f"{observation.source}:{observation.observed_at.isoformat()}"
            device_id = f"discovered-{uuid5(NAMESPACE_URL, f'devicemesh:{stable_key}')}"
            device = Device(id=device_id, first_seen=observation.observed_at)
            self._devices[device_id] = device

        device.hostname = observation.hostname or device.hostname
        device.manufacturer = observation.manufacturer or device.manufacturer
        if observation.ip_address:
            device.ip_addresses = {observation.ip_address}
        if observation.mac_address:
            device.mac_addresses.add(observation.mac_address.upper().replace("-", ":"))
        device.status = DeviceStatus.ONLINE
        device.last_seen = observation.observed_at
        return device

    def _find_observed_device(self, observation: DeviceObservation) -> Device | None:
        normalized_mac = (
            observation.mac_address.upper().replace("-", ":")
            if observation.mac_address
            else None
        )
        if normalized_mac:
            for device in self._devices.values():
                if normalized_mac in device.mac_addresses:
                    return device
        if observation.hostname:
            for device in self._devices.values():
                if device.hostname == observation.hostname:
                    return device
        if observation.ip_address:
            for device in self._devices.values():
                if observation.ip_address in device.ip_addresses:
                    return device
        return None


class InMemoryTelemetryRepository:
    def __init__(self) -> None:
        self.batches: list[TelemetryBatch] = []

    def append(self, batch: TelemetryBatch) -> None:
        self.batches.append(batch)

    def list_latest(self) -> list[MetricSample]:
        latest: dict[tuple[str, str], MetricSample] = {}
        for batch in self.batches:
            for metric in batch.metrics:
                key = (batch.agent_id, metric.name)
                existing = latest.get(key)
                if existing is None or batch.timestamp > existing.timestamp:
                    latest[key] = MetricSample(batch.agent_id, batch.timestamp, metric)
        return list(latest.values())
