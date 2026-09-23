from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.use_cases.record_telemetry import RecordTelemetry
from app.domain.alerts.models import ThresholdRule
from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.alerting_telemetry import AlertingTelemetryRepository
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyTelemetryRepository
from app.runtime import device_repository, event_repository, telemetry_use_case


def _register_agent(agent_id: str, timestamp: datetime) -> None:
    device_repository.mark_agent_online(
        agent_id,
        timestamp,
        DeviceIdentity(hostname=agent_id),
    )


def _batch(agent_id: str, timestamp: datetime, metric_name: str, value: float) -> TelemetryBatch:
    return TelemetryBatch(
        agent_id=agent_id,
        timestamp=timestamp,
        metrics=(Metric(metric_name, value, "%"),),
    )


def test_threshold_alert_opens_once_and_recovers_once() -> None:
    metric_name = f"test.cpu.{uuid4().hex}"
    agent_id = f"alert-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register_agent(agent_id, now)
    repository = SqlAlchemyAlertRepository(SessionFactory)
    rule = repository.create_rule(ThresholdRule(metric_name, ">", 90.0))

    violating = _batch(agent_id, now + timedelta(seconds=1), metric_name, 95.0)
    telemetry_use_case.execute(violating)
    telemetry_use_case.execute(violating)

    active = [item for item in repository.list_alerts(active_only=True) if item.rule_id == rule.id]
    assert len(active) == 1

    telemetry_use_case.execute(
        _batch(agent_id, now + timedelta(seconds=2), metric_name, 42.0)
    )
    assert not [
        item for item in repository.list_alerts(active_only=True) if item.rule_id == rule.id
    ]
    history = [item for item in repository.list_alerts() if item.rule_id == rule.id]
    assert len(history) == 1
    assert history[0].closed_at is not None

    names = [
        event.name
        for event in event_repository.list_recent(200)
        if event.attributes.get("ruleId") == rule.id
    ]
    assert names.count("ALERT_OPENED") == 1
    assert names.count("ALERT_RECOVERED") == 1


def test_alert_duration_state_survives_repository_recreation() -> None:
    metric_name = f"test.ram.{uuid4().hex}"
    agent_id = f"duration-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register_agent(agent_id, now)
    first_repository = SqlAlchemyAlertRepository(SessionFactory)
    rule = first_repository.create_rule(ThresholdRule(metric_name, ">=", 80.0, 60))

    telemetry_use_case.execute(_batch(agent_id, now, metric_name, 88.0))
    assert not [
        item for item in first_repository.list_alerts(active_only=True) if item.rule_id == rule.id
    ]

    restarted_repository = SqlAlchemyAlertRepository(SessionFactory)
    restarted_telemetry = RecordTelemetry(
        AlertingTelemetryRepository(
            SqlAlchemyTelemetryRepository(SessionFactory),
            restarted_repository,
            event_repository,
        )
    )
    restarted_telemetry.execute(
        _batch(agent_id, now + timedelta(seconds=61), metric_name, 85.0)
    )
    active = [
        item
        for item in restarted_repository.list_alerts(active_only=True)
        if item.rule_id == rule.id
    ]
    assert len(active) == 1


def test_recovery_before_duration_resets_pending_condition() -> None:
    metric_name = f"test.latency.{uuid4().hex}"
    agent_id = f"reset-agent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    _register_agent(agent_id, now)
    repository = SqlAlchemyAlertRepository(SessionFactory)
    rule = repository.create_rule(ThresholdRule(metric_name, ">", 100.0, 60))

    telemetry_use_case.execute(_batch(agent_id, now, metric_name, 150.0))
    telemetry_use_case.execute(
        _batch(agent_id, now + timedelta(seconds=30), metric_name, 50.0)
    )
    telemetry_use_case.execute(
        _batch(agent_id, now + timedelta(seconds=70), metric_name, 150.0)
    )
    telemetry_use_case.execute(
        _batch(agent_id, now + timedelta(seconds=100), metric_name, 150.0)
    )
    assert not [
        item for item in repository.list_alerts(active_only=True) if item.rule_id == rule.id
    ]

    telemetry_use_case.execute(
        _batch(agent_id, now + timedelta(seconds=131), metric_name, 150.0)
    )
    assert len(
        [item for item in repository.list_alerts(active_only=True) if item.rule_id == rule.id]
    ) == 1
