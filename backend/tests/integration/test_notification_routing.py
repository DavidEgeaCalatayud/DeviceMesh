from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.domain.alerts.models import (
    AlertIncident,
    AlertRule,
    AlertTransition,
    AlertTransitionType,
    ThresholdRule,
)
from app.domain.alerts.notifications import (
    NotificationChannel,
    NotificationChannelKind,
    NotificationDeliveryStatus,
    NotificationTransitionFilter,
)
from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.notification_delivery import NotificationDispatcher
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.infrastructure.repositories.notifications import SqlAlchemyNotificationRepository
from app.runtime import device_repository, telemetry_use_case


def _register(agent_id: str, timestamp: datetime) -> None:
    device_repository.mark_agent_online(
        agent_id,
        timestamp,
        DeviceIdentity(hostname=agent_id),
    )


def _batch(agent_id: str, timestamp: datetime, metric: str, value: float) -> TelemetryBatch:
    return TelemetryBatch(
        agent_id=agent_id,
        timestamp=timestamp,
        metrics=(Metric(metric, value, "%"),),
    )


class _SecretResolver:
    def resolve(self, secret_ref: str) -> str:
        return f"secret-for-{secret_ref}"


class _RecordingTransport:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[int, dict[str, object], str]] = []

    def send(
        self,
        channel: NotificationChannel,
        payload: dict[str, object],
        secret: str,
    ) -> None:
        if self.fail:
            raise RuntimeError("destination unavailable")
        self.sent.append((channel.id, payload, secret))


def _configure_route(metric: str) -> tuple[SqlAlchemyNotificationRepository, int]:
    repository = SqlAlchemyNotificationRepository(SessionFactory)
    suffix = uuid4().hex
    channel = repository.create_channel(
        name=f"test-channel-{suffix}",
        kind=NotificationChannelKind.WEBHOOK,
        secret_ref=f"hook-{suffix}",
        config={},
    )
    repository.create_route(
        name=f"test-route-{suffix}",
        channel_id=channel.id,
        transition=NotificationTransitionFilter.BOTH,
        metric_name=metric,
        device_id=None,
    )
    return repository, channel.id


def test_alert_transition_routes_once_and_recovery_routes_once() -> None:
    metric = f"notify.cpu.{uuid4().hex}"
    repository, channel_id = _configure_route(metric)
    alerts = SqlAlchemyAlertRepository(SessionFactory)
    rule = alerts.create_rule(ThresholdRule(metric, ">", 90.0))
    agent_id = f"notify-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register(agent_id, now)

    violating = _batch(agent_id, now + timedelta(seconds=1), metric, 95.0)
    telemetry_use_case.execute(violating)
    telemetry_use_case.execute(violating)

    alert_ids = {alert.id for alert in alerts.list_alerts() if alert.rule_id == rule.id}
    opened = [
        delivery
        for delivery in repository.list_deliveries(limit=500)
        if delivery.channel_id == channel_id and delivery.alert_id in alert_ids
    ]
    assert len(opened) == 1
    assert opened[0].transition == "opened"

    telemetry_use_case.execute(_batch(agent_id, now + timedelta(seconds=2), metric, 20.0))
    deliveries = [
        delivery
        for delivery in repository.list_deliveries(limit=500)
        if delivery.channel_id == channel_id
    ]
    assert [delivery.transition for delivery in deliveries].count("opened") == 1
    assert [delivery.transition for delivery in deliveries].count("recovered") == 1


def test_maintenance_transition_is_not_enqueued() -> None:
    metric = f"notify.maintenance.{uuid4().hex}"
    repository, _ = _configure_route(metric)
    transition = AlertTransition(
        type=AlertTransitionType.OPENED,
        incident=AlertIncident(
            id=999_999_999,
            rule_id=999_999_998,
            device_id="maintenance-device",
            opened_at=datetime.now(UTC),
            maintenance_window_id=123,
        ),
        rule=AlertRule(
            id=999_999_998,
            condition=ThresholdRule(metric, ">", 1.0),
        ),
        value=2.0,
        timestamp=datetime.now(UTC),
    )
    assert repository.enqueue_transition(transition) == 0


def test_dispatcher_delivers_without_exposing_secret() -> None:
    metric = f"notify.delivery.{uuid4().hex}"
    repository, channel_id = _configure_route(metric)
    alerts = SqlAlchemyAlertRepository(SessionFactory)
    alerts.create_rule(ThresholdRule(metric, ">", 10.0))
    agent_id = f"delivery-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register(agent_id, now)
    telemetry_use_case.execute(_batch(agent_id, now + timedelta(seconds=1), metric, 20.0))

    transport = _RecordingTransport()
    dispatcher = NotificationDispatcher(
        repository,
        _SecretResolver(),  # type: ignore[arg-type]
        transport,  # type: ignore[arg-type]
        Settings(notification_delivery_batch_size=500),
    )
    delivered, failed = dispatcher.run_due(now + timedelta(seconds=2))
    assert delivered >= 1
    assert failed == 0
    assert any(item[0] == channel_id for item in transport.sent)
    mine = [
        delivery
        for delivery in repository.list_deliveries(limit=500)
        if delivery.channel_id == channel_id
    ]
    assert mine and mine[0].status is NotificationDeliveryStatus.DELIVERED
    assert all("secret-for-" not in str(delivery.payload) for delivery in mine)


def test_dispatcher_retries_then_dead_letters() -> None:
    metric = f"notify.retry.{uuid4().hex}"
    repository, channel_id = _configure_route(metric)
    alerts = SqlAlchemyAlertRepository(SessionFactory)
    alerts.create_rule(ThresholdRule(metric, ">", 10.0))
    agent_id = f"retry-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register(agent_id, now)
    telemetry_use_case.execute(_batch(agent_id, now + timedelta(seconds=1), metric, 20.0))

    dispatcher = NotificationDispatcher(
        repository,
        _SecretResolver(),  # type: ignore[arg-type]
        _RecordingTransport(fail=True),  # type: ignore[arg-type]
        Settings(
            notification_delivery_batch_size=500,
            notification_delivery_max_attempts=2,
        ),
    )
    _, first_failed = dispatcher.run_due(now + timedelta(seconds=2))
    assert first_failed >= 1
    _, second_failed = dispatcher.run_due(now + timedelta(seconds=10))
    assert second_failed >= 1
    mine = [
        delivery
        for delivery in repository.list_deliveries(limit=500)
        if delivery.channel_id == channel_id
    ]
    assert mine and mine[0].status is NotificationDeliveryStatus.DEAD
    assert mine[0].attempts == 2
    assert mine[0].last_error == "RuntimeError"
