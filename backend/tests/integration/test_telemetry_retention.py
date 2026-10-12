from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.database import (
    AlertRow,
    AlertRuleRow,
    DeviceEventRow,
    DeviceObservationRow,
    MetricSampleRow,
    SecurityAuditEventRow,
    SessionFactory,
)
from app.infrastructure.repositories.nms import NetworkInterfaceCounterRow
from app.infrastructure.repositories.notifications import (
    NotificationChannelRow,
    NotificationDeliveryRow,
    NotificationRouteRow,
)
from app.infrastructure.repositories.retention import (
    MetricHourlyRollupRow,
    SqlAlchemyTelemetryRetentionRepository,
)
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyDeviceRepository,
    SqlAlchemyTelemetryRepository,
)
from app.infrastructure.repositories.synthetics import SyntheticCheckResultRow, SyntheticMonitorRow
from app.infrastructure.repositories.syslog import SyslogMessageRow
from app.infrastructure.security.human_auth import AuditRow


def test_compaction_preserves_hourly_statistics_and_merges_late_samples() -> None:
    agent_id = f"retention-{uuid4()}"
    now = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
    sample_hour = now - timedelta(days=2)
    cutoff = now - timedelta(days=1)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    telemetry = SqlAlchemyTelemetryRepository(SessionFactory)
    retention = SqlAlchemyTelemetryRetentionRepository(SessionFactory)
    devices.mark_agent_online(agent_id, sample_hour, DeviceIdentity(hostname="retention-test"))

    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour,
            metrics=(Metric("network.latency.ms", 10.0, "ms"),),
        )
    )
    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour + timedelta(minutes=10),
            metrics=(Metric("network.latency.ms", 20.0, "ms"),),
        )
    )

    first = retention.compact_before(cutoff)
    assert first.raw_samples_deleted >= 2
    raw = telemetry.list_history(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    assert raw.points == ()

    hourly = retention.list_hourly(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    assert len(hourly.points) == 1
    point = hourly.points[0]
    assert point.average == 15.0
    assert point.minimum == 10.0
    assert point.maximum == 20.0
    assert point.samples == 2
    assert point.unit == "ms"

    second = retention.compact_before(cutoff)
    assert second.raw_samples_deleted == 0

    telemetry.append(
        TelemetryBatch(
            agent_id=agent_id,
            timestamp=sample_hour + timedelta(minutes=20),
            metrics=(Metric("network.latency.ms", 30.0, "ms"),),
        )
    )
    third = retention.compact_before(cutoff)
    assert third.raw_samples_deleted == 1

    merged = retention.list_hourly(
        agent_id,
        "network.latency.ms",
        sample_hour - timedelta(hours=1),
        sample_hour + timedelta(hours=1),
    )
    merged_point = merged.points[0]
    assert merged_point.average == 20.0
    assert merged_point.minimum == 10.0
    assert merged_point.maximum == 30.0
    assert merged_point.samples == 3


def test_policy_compacts_raw_and_expires_archived_operational_data() -> None:
    agent_id = f"retention-policy-{uuid4()}"
    monitor_id = str(uuid4())
    now = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
    very_old = now - timedelta(days=400)
    recent_raw = now - timedelta(days=10)
    expired_operational = now - timedelta(days=100)
    expired_audit = now - timedelta(days=800)

    devices = SqlAlchemyDeviceRepository(SessionFactory)
    devices.mark_agent_online(agent_id, now, DeviceIdentity(hostname="retention-policy-test"))
    with SessionFactory.begin() as session:
        session.add_all([
            MetricSampleRow(device_id=agent_id, metric_type="cpu.usage", timestamp=very_old,
                            value=12.0, unit="percent"),
            MetricSampleRow(device_id=agent_id, metric_type="cpu.usage", timestamp=recent_raw,
                            value=42.0, unit="percent"),
            DeviceEventRow(device_id=agent_id, name="test.expired", severity="info",
                           timestamp=expired_operational, attributes={}),
            SyntheticMonitorRow(id=monitor_id, name="retention", kind="http",
                                target="https://example.com", port=None, device_id=agent_id,
                                interval_seconds=60, timeout_seconds=5, enabled=True,
                                http_method="GET", expected_status=200, failure_threshold=3,
                                recovery_threshold=2, created_by="test", created_at=now,
                                updated_at=now, next_run_at=now),
        ])
        session.flush()
        session.add(SyntheticCheckResultRow(
            monitor_id=monitor_id, checked_at=expired_operational, success=True,
            latency_ms=10, http_status=200, error_kind=None, error=None,
            probe_id="test", probe_location=None, work_id=None,
        ))

        session.add_all([
            DeviceObservationRow(
                device_id=agent_id,
                source="retention-test",
                observed_at=expired_operational,
                hostname="expired-observation",
                ip_address="10.250.0.10",
                mac_address=None,
                manufacturer=None,
                network_cidr="10.250.0.0/24",
                attributes={},
            ),
            NetworkInterfaceCounterRow(
                device_id=agent_id,
                interface_name="eth0",
                sampled_at=expired_operational,
                in_octets=1,
                out_octets=2,
                in_errors=0,
                out_errors=0,
            ),
            SyslogMessageRow(
                received_at=expired_operational,
                source_address="10.250.0.10",
                device_id=agent_id,
                facility=16,
                severity=5,
                hostname="retention-policy-test",
                app_name="test",
                proc_id=None,
                msg_id=None,
                message="expired syslog",
                protocol="rfc5424",
            ),
            AuditRow(
                id=str(uuid4()),
                actor="retention-test",
                action="expired.audit",
                resource="test",
                timestamp=expired_audit,
                source_ip=None,
                request_id=None,
                details={},
            ),
            SecurityAuditEventRow(
                event_type="EXPIRED_SECURITY_AUDIT",
                agent_id=agent_id,
                occurred_at=expired_audit,
                attributes={},
            ),
        ])

        rule = AlertRuleRow(
            metric_name="retention.metric",
            operator=">",
            threshold=1.0,
            duration_seconds=0,
            enabled=True,
        )
        channel = NotificationChannelRow(
            name=f"retention-channel-{uuid4()}",
            kind="webhook",
            secret_ref="retention-test",
            config={},
            enabled=True,
        )
        session.add_all([rule, channel])
        session.flush()
        alert = AlertRow(
            rule_id=rule.id,
            device_id=agent_id,
            opened_at=expired_operational,
            closed_at=expired_operational,
            maintenance_window_id=None,
        )
        route = NotificationRouteRow(
            name=f"retention-route-{uuid4()}",
            channel_id=channel.id,
            transition="both",
            metric_name=None,
            device_id=agent_id,
            enabled=True,
        )
        session.add_all([alert, route])
        session.flush()
        session.add(
            NotificationDeliveryRow(
                channel_id=channel.id,
                route_id=route.id,
                alert_id=alert.id,
                transition="recovered",
                dedupe_key=f"retention:{uuid4()}",
                payload={},
                status="delivered",
                attempts=1,
                next_attempt_at=expired_operational,
                locked_until=None,
                last_attempt_at=expired_operational,
                delivered_at=expired_operational,
                last_error=None,
                created_at=expired_operational,
            )
        )

    retention = SqlAlchemyTelemetryRetentionRepository(SessionFactory)
    result = retention.enforce_policy(
        now,
        raw_retention_days=7,
        hourly_retention_days=365,
        event_retention_days=90,
        synthetic_check_retention_days=90,
        discovery_observation_retention_days=30,
        nms_counter_retention_days=90,
        syslog_retention_days=90,
        audit_retention_days=730,
        security_audit_retention_days=730,
        notification_delivery_retention_days=90,
    )

    assert result.raw_samples_deleted >= 2
    assert result.hourly_rollups_deleted >= 1
    assert result.events_deleted >= 1
    assert result.synthetic_checks_deleted >= 1
    assert result.discovery_observations_deleted >= 1
    assert result.nms_counters_deleted >= 1
    assert result.syslog_messages_deleted >= 1
    assert result.audit_events_deleted >= 1
    assert result.security_audit_events_deleted >= 1
    assert result.notification_deliveries_deleted >= 1
    with SessionFactory() as session:
        assert session.scalar(select(MetricSampleRow.id).where(MetricSampleRow.device_id == agent_id)) is None
        hourly = list(session.scalars(select(MetricHourlyRollupRow).where(
            MetricHourlyRollupRow.device_id == agent_id
        )))
        assert len(hourly) == 1
        assert hourly[0].bucket_start.date() == recent_raw.date()
        assert session.scalar(select(DeviceEventRow.id).where(
            DeviceEventRow.device_id == agent_id,
            DeviceEventRow.name == "test.expired",
        )) is None
        assert session.scalar(select(SyntheticCheckResultRow.id).where(
            SyntheticCheckResultRow.monitor_id == monitor_id
        )) is None
        assert session.scalar(select(DeviceObservationRow.id).where(
            DeviceObservationRow.device_id == agent_id,
            DeviceObservationRow.source == "retention-test",
        )) is None
        assert session.scalar(select(NetworkInterfaceCounterRow.id).where(
            NetworkInterfaceCounterRow.device_id == agent_id
        )) is None
        assert session.scalar(select(SyslogMessageRow.id).where(
            SyslogMessageRow.device_id == agent_id
        )) is None
        assert session.scalar(select(AuditRow.id).where(
            AuditRow.action == "expired.audit"
        )) is None
        assert session.scalar(select(SecurityAuditEventRow.id).where(
            SecurityAuditEventRow.event_type == "EXPIRED_SECURITY_AUDIT"
        )) is None
        assert session.scalar(select(NotificationDeliveryRow.id).where(
            NotificationDeliveryRow.alert_id == alert.id
        )) is None
