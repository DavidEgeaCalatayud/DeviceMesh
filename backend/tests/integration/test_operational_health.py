from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.alerts.models import ThresholdRule
from app.domain.devices.models import DeviceIdentity
from app.domain.health.models import AvailabilityState
from app.domain.operations.models import RemoteOperationStatus, RemoteOperationType
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.alerts import SqlAlchemyAlertRepository
from app.infrastructure.repositories.health import (
    SqlAlchemyHealthRepository,
    SqlAlchemyMaintenanceRepository,
)
from app.infrastructure.repositories.operations import (
    RemoteOperationNotFoundError,
    SqlAlchemyRemoteOperationRepository,
)
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyDeviceRepository


def test_sla_summary_counts_outages_and_current_downtime() -> None:
    device_id = f"health-{uuid4()}"
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=5)
    now = start + timedelta(hours=5)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    health = SqlAlchemyHealthRepository(SessionFactory)
    devices.mark_agent_online(device_id, start, DeviceIdentity(hostname="health-test"))

    health.record_state(device_id, AvailabilityState.ONLINE, start, "test")
    health.record_state(device_id, AvailabilityState.OFFLINE, start + timedelta(hours=2), "test")
    health.record_state(device_id, AvailabilityState.ONLINE, start + timedelta(hours=3), "test")
    health.record_state(device_id, AvailabilityState.OFFLINE, start + timedelta(hours=4), "test")

    summary = health.summarize(device_id, now)
    day = next(window for window in summary.windows if window.label == "24h")

    assert day.monitored_seconds == 5 * 3600
    assert day.online_seconds == 3 * 3600
    assert day.downtime_seconds == 2 * 3600
    assert day.availability_percent == pytest.approx(60.0)
    assert day.outage_count == 2
    assert day.longest_outage_seconds == 3600
    assert day.mean_recovery_seconds == 3600
    assert summary.current_state is AvailabilityState.OFFLINE
    assert summary.current_outage_seconds == 3600


def test_maintenance_preserves_incident_but_marks_it_silenced() -> None:
    agent_id = f"maintenance-{uuid4()}"
    now = datetime.now(UTC).replace(microsecond=0)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    maintenance = SqlAlchemyMaintenanceRepository(SessionFactory)
    alerts = SqlAlchemyAlertRepository(SessionFactory, maintenance)
    devices.mark_agent_online(agent_id, now, DeviceIdentity(hostname="maintenance-test"))

    window = maintenance.create(
        device_id=agent_id,
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(minutes=30),
        reason="planned patching",
        created_at=now,
    )
    rule = alerts.create_rule(ThresholdRule("host.cpu.utilization.percent", ">=", 90.0))
    transitions = alerts.evaluate(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=now,
            metrics=(Metric("host.cpu.utilization.percent", 95.0, "percent"),),
        )
    )

    assert len(transitions) == 1
    incident = transitions[0].incident
    assert incident.rule_id == rule.id
    assert incident.maintenance_window_id == window.id
    assert alerts.list_alerts(active_only=True)[0].maintenance_window_id == window.id


def test_remote_operations_are_allowlisted_claimed_and_completed_by_target_agent() -> None:
    agent_id = f"operations-{uuid4()}"
    now = datetime.now(UTC).replace(microsecond=0)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    operations = SqlAlchemyRemoteOperationRepository(SessionFactory)
    devices.mark_agent_online(agent_id, now, DeviceIdentity(hostname="operations-test"))

    queued = operations.queue(
        device_id=agent_id,
        operation_type=RemoteOperationType.AGENT_HEALTH_CHECK,
        now=now,
    )
    assert queued.status is RemoteOperationStatus.QUEUED

    claimed = operations.claim_next(agent_id, now=now + timedelta(seconds=1))
    assert claimed is not None
    assert claimed.id == queued.id
    assert claimed.status is RemoteOperationStatus.CLAIMED

    with pytest.raises(RemoteOperationNotFoundError):
        operations.complete(
            agent_id="different-agent",
            operation_id=queued.id,
            succeeded=True,
            now=now + timedelta(seconds=2),
        )

    completed = operations.complete(
        agent_id=agent_id,
        operation_id=queued.id,
        succeeded=True,
        result={"status": "ok"},
        now=now + timedelta(seconds=2),
    )
    assert completed.status is RemoteOperationStatus.SUCCEEDED
    assert completed.result == {"status": "ok"}

    with pytest.raises(ValueError):
        operations.queue(
            device_id=agent_id,
            operation_type=RemoteOperationType.TELEMETRY_COLLECT,
            arguments={"command": "whoami"},
            now=now,
        )
