from datetime import datetime

from app.application.ports import AlertRepository, EventRepository, TelemetryRepository
from app.domain.alerts.models import AlertTransition, AlertTransitionType
from app.domain.events.models import DeviceEvent, EventSeverity
from app.domain.telemetry.models import MetricSample, MetricSeries, TelemetryBatch


class AlertingTelemetryRepository:
    def __init__(
        self,
        telemetry: TelemetryRepository,
        alerts: AlertRepository,
        events: EventRepository,
    ) -> None:
        self._telemetry = telemetry
        self._alerts = alerts
        self._events = events

    def append(self, batch: TelemetryBatch) -> None:
        self._telemetry.append(batch)
        for transition in self._alerts.evaluate(batch):
            self._events.append(self._to_event(transition))

    def list_latest(self) -> list[MetricSample]:
        return self._telemetry.list_latest()

    def list_history(
        self,
        device_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 1000,
        bucket_seconds: int | None = None,
    ) -> MetricSeries:
        return self._telemetry.list_history(
            device_id,
            metric_name,
            start,
            end,
            limit=limit,
            bucket_seconds=bucket_seconds,
        )

    @staticmethod
    def _to_event(transition: AlertTransition) -> DeviceEvent:
        condition = transition.rule.condition
        opened = transition.type is AlertTransitionType.OPENED
        return DeviceEvent(
            device_id=transition.incident.device_id,
            name="ALERT_OPENED" if opened else "ALERT_RECOVERED",
            timestamp=transition.timestamp,
            severity=EventSeverity.WARNING if opened else EventSeverity.INFO,
            attributes={
                "alertId": transition.incident.id,
                "ruleId": transition.rule.id,
                "metricName": condition.metric_name,
                "operator": condition.operator,
                "threshold": condition.threshold,
                "durationSeconds": condition.duration_seconds,
                "value": transition.value,
            },
        )
