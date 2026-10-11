from datetime import datetime
from typing import Protocol

from app.domain.alerts.models import AlertIncident, AlertRule, AlertTransition, ThresholdRule
from app.domain.devices.models import Device, DeviceIdentity, DeviceObservation
from app.domain.events.models import DeviceEvent
from app.domain.network.models import (
    DeviceService,
    NetworkInterfaceInventory,
    NetworkTopology,
    ServiceTransition,
)
from app.domain.telemetry.models import MetricSample, MetricSeries, TelemetryBatch


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

    def list_history(
        self,
        device_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 1000,
        bucket_seconds: int | None = None,
    ) -> MetricSeries: ...


class EventRepository(Protocol):
    def append(self, event: DeviceEvent) -> None: ...

    def list_recent(self, limit: int = 100) -> list[DeviceEvent]: ...


class AlertRepository(Protocol):
    def create_rule(self, rule: ThresholdRule) -> AlertRule: ...

    def list_rules(self) -> list[AlertRule]: ...

    def list_alerts(self, *, active_only: bool = False, limit: int = 100) -> list[AlertIncident]: ...

    def evaluate(self, batch: TelemetryBatch) -> list[AlertTransition]: ...


class NetworkRepository(Protocol):
    def reconcile_interfaces(self, device_id: str, observation: DeviceObservation) -> None: ...

    def list_interfaces(
        self,
        *,
        device_id: str | None = None,
        present_only: bool = True,
    ) -> list[NetworkInterfaceInventory]: ...

    def reconcile_services(
        self,
        device_id: str,
        observation: DeviceObservation,
    ) -> list[ServiceTransition]: ...

    def list_services(
        self,
        *,
        device_id: str | None = None,
        active_only: bool = True,
    ) -> list[DeviceService]: ...

    def get_topology(self) -> NetworkTopology: ...
