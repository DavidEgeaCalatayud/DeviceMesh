from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.database import (
    Base,
    DeviceEventRow,
    DeviceObservationRow,
    MetricSampleRow,
    SecurityAuditEventRow,
)
from app.infrastructure.repositories.nms import NetworkInterfaceCounterRow
from app.infrastructure.repositories.notifications import NotificationDeliveryRow
from app.infrastructure.repositories.synthetics import SyntheticCheckResultRow
from app.infrastructure.repositories.syslog import SyslogMessageRow
from app.infrastructure.security.human_auth import AuditRow


class MetricHourlyRollupRow(Base):
    __tablename__ = "metric_hourly_rollups"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "metric_type",
            "bucket_start",
            name="uq_metric_hourly_rollup_bucket",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(128), nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    average: Mapped[float] = mapped_column(Float, nullable=False)
    minimum: Mapped[float] = mapped_column(Float, nullable=False)
    maximum: Mapped[float] = mapped_column(Float, nullable=False)
    samples: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))


@dataclass(frozen=True, slots=True)
class HourlyMetricPoint:
    timestamp: datetime
    average: float
    minimum: float
    maximum: float
    samples: int
    unit: str | None


@dataclass(frozen=True, slots=True)
class HourlyMetricSeries:
    device_id: str
    metric_name: str
    start: datetime
    end: datetime
    points: tuple[HourlyMetricPoint, ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class TelemetryCompactionResult:
    cutoff: datetime
    rollups_touched: int
    raw_samples_deleted: int


@dataclass(frozen=True, slots=True)
class RetentionPolicyResult:
    raw_cutoff: datetime
    hourly_cutoff: datetime
    event_cutoff: datetime
    synthetic_cutoff: datetime
    discovery_cutoff: datetime
    nms_counter_cutoff: datetime
    syslog_cutoff: datetime
    audit_cutoff: datetime
    security_audit_cutoff: datetime
    notification_delivery_cutoff: datetime
    rollups_touched: int
    raw_samples_deleted: int
    hourly_rollups_deleted: int
    events_deleted: int
    synthetic_checks_deleted: int
    discovery_observations_deleted: int
    nms_counters_deleted: int
    syslog_messages_deleted: int
    audit_events_deleted: int
    security_audit_events_deleted: int
    notification_deliveries_deleted: int


class SqlAlchemyTelemetryRetentionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def compact_before(self, cutoff: datetime) -> TelemetryCompactionResult:
        if cutoff.tzinfo is None:
            raise ValueError("cutoff must include a timezone")

        bucket_start = func.date_trunc("hour", MetricSampleRow.timestamp).label("bucket_start")
        statement = (
            select(
                MetricSampleRow.device_id,
                MetricSampleRow.metric_type,
                bucket_start,
                func.avg(MetricSampleRow.value).label("average"),
                func.min(MetricSampleRow.value).label("minimum"),
                func.max(MetricSampleRow.value).label("maximum"),
                func.count(MetricSampleRow.id).label("samples"),
                func.max(MetricSampleRow.unit).label("unit"),
            )
            .where(MetricSampleRow.timestamp < cutoff)
            .group_by(MetricSampleRow.device_id, MetricSampleRow.metric_type, bucket_start)
            .order_by(MetricSampleRow.device_id, MetricSampleRow.metric_type, bucket_start)
        )

        with self._session_factory() as session:
            aggregates = session.execute(statement).all()
            for row in aggregates:
                timestamp = row.bucket_start
                existing = session.scalar(
                    select(MetricHourlyRollupRow)
                    .where(
                        MetricHourlyRollupRow.device_id == row.device_id,
                        MetricHourlyRollupRow.metric_type == row.metric_type,
                        MetricHourlyRollupRow.bucket_start == timestamp,
                    )
                    .limit(1)
                )
                incoming_samples = int(row.samples)
                incoming_average = float(row.average)
                incoming_minimum = float(row.minimum)
                incoming_maximum = float(row.maximum)
                if existing is None:
                    session.add(
                        MetricHourlyRollupRow(
                            device_id=row.device_id,
                            metric_type=row.metric_type,
                            bucket_start=timestamp,
                            average=incoming_average,
                            minimum=incoming_minimum,
                            maximum=incoming_maximum,
                            samples=incoming_samples,
                            unit=row.unit,
                        )
                    )
                    continue

                total_samples = existing.samples + incoming_samples
                existing.average = (
                    (existing.average * existing.samples) + (incoming_average * incoming_samples)
                ) / total_samples
                existing.minimum = min(existing.minimum, incoming_minimum)
                existing.maximum = max(existing.maximum, incoming_maximum)
                existing.samples = total_samples
                existing.unit = existing.unit or row.unit

            raw_samples_deleted = session.scalar(
                select(func.count(MetricSampleRow.id)).where(MetricSampleRow.timestamp < cutoff)
            ) or 0
            session.flush()
            session.execute(delete(MetricSampleRow).where(MetricSampleRow.timestamp < cutoff))
            session.commit()

        return TelemetryCompactionResult(
            cutoff=cutoff,
            rollups_touched=len(aggregates),
            raw_samples_deleted=raw_samples_deleted,
        )

    def enforce_policy(
        self,
        now: datetime,
        *,
        raw_retention_days: int,
        hourly_retention_days: int,
        event_retention_days: int,
        synthetic_check_retention_days: int,
        discovery_observation_retention_days: int,
        nms_counter_retention_days: int,
        syslog_retention_days: int,
        audit_retention_days: int,
        security_audit_retention_days: int,
        notification_delivery_retention_days: int,
    ) -> RetentionPolicyResult:
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        if hourly_retention_days <= raw_retention_days:
            raise ValueError("hourly retention must exceed raw retention")

        raw_cutoff = now - timedelta(days=raw_retention_days)
        hourly_cutoff = now - timedelta(days=hourly_retention_days)
        event_cutoff = now - timedelta(days=event_retention_days)
        synthetic_cutoff = now - timedelta(days=synthetic_check_retention_days)
        discovery_cutoff = now - timedelta(days=discovery_observation_retention_days)
        nms_counter_cutoff = now - timedelta(days=nms_counter_retention_days)
        syslog_cutoff = now - timedelta(days=syslog_retention_days)
        audit_cutoff = now - timedelta(days=audit_retention_days)
        security_audit_cutoff = now - timedelta(days=security_audit_retention_days)
        notification_delivery_cutoff = now - timedelta(days=notification_delivery_retention_days)

        compaction = self.compact_before(raw_cutoff)
        with self._session_factory.begin() as session:
            def count_before(model: type[Base], column: object, cutoff: datetime) -> int:
                primary_key = next(iter(model.__table__.primary_key.columns))
                count = session.scalar(select(func.count(primary_key)).where(column < cutoff)) or 0
                return int(count)

            hourly_rollups_deleted = count_before(
                MetricHourlyRollupRow,
                MetricHourlyRollupRow.bucket_start,
                hourly_cutoff,
            )
            events_deleted = count_before(DeviceEventRow, DeviceEventRow.timestamp, event_cutoff)
            synthetic_checks_deleted = count_before(
                SyntheticCheckResultRow,
                SyntheticCheckResultRow.checked_at,
                synthetic_cutoff,
            )
            discovery_observations_deleted = count_before(
                DeviceObservationRow,
                DeviceObservationRow.observed_at,
                discovery_cutoff,
            )
            nms_counters_deleted = count_before(
                NetworkInterfaceCounterRow,
                NetworkInterfaceCounterRow.sampled_at,
                nms_counter_cutoff,
            )
            syslog_messages_deleted = count_before(
                SyslogMessageRow,
                SyslogMessageRow.received_at,
                syslog_cutoff,
            )
            audit_events_deleted = count_before(AuditRow, AuditRow.timestamp, audit_cutoff)
            security_audit_events_deleted = count_before(
                SecurityAuditEventRow,
                SecurityAuditEventRow.occurred_at,
                security_audit_cutoff,
            )
            notification_deliveries_deleted = count_before(
                NotificationDeliveryRow,
                NotificationDeliveryRow.created_at,
                notification_delivery_cutoff,
            )

            session.execute(
                delete(MetricHourlyRollupRow).where(
                    MetricHourlyRollupRow.bucket_start < hourly_cutoff
                )
            )
            session.execute(delete(DeviceEventRow).where(DeviceEventRow.timestamp < event_cutoff))
            session.execute(
                delete(SyntheticCheckResultRow).where(
                    SyntheticCheckResultRow.checked_at < synthetic_cutoff
                )
            )
            session.execute(
                delete(DeviceObservationRow).where(
                    DeviceObservationRow.observed_at < discovery_cutoff
                )
            )
            session.execute(
                delete(NetworkInterfaceCounterRow).where(
                    NetworkInterfaceCounterRow.sampled_at < nms_counter_cutoff
                )
            )
            session.execute(
                delete(SyslogMessageRow).where(SyslogMessageRow.received_at < syslog_cutoff)
            )
            session.execute(delete(AuditRow).where(AuditRow.timestamp < audit_cutoff))
            session.execute(
                delete(SecurityAuditEventRow).where(
                    SecurityAuditEventRow.occurred_at < security_audit_cutoff
                )
            )
            session.execute(
                delete(NotificationDeliveryRow).where(
                    NotificationDeliveryRow.created_at < notification_delivery_cutoff
                )
            )

        return RetentionPolicyResult(
            raw_cutoff=raw_cutoff,
            hourly_cutoff=hourly_cutoff,
            event_cutoff=event_cutoff,
            synthetic_cutoff=synthetic_cutoff,
            discovery_cutoff=discovery_cutoff,
            nms_counter_cutoff=nms_counter_cutoff,
            syslog_cutoff=syslog_cutoff,
            audit_cutoff=audit_cutoff,
            security_audit_cutoff=security_audit_cutoff,
            notification_delivery_cutoff=notification_delivery_cutoff,
            rollups_touched=compaction.rollups_touched,
            raw_samples_deleted=compaction.raw_samples_deleted,
            hourly_rollups_deleted=hourly_rollups_deleted,
            events_deleted=events_deleted,
            synthetic_checks_deleted=synthetic_checks_deleted,
            discovery_observations_deleted=discovery_observations_deleted,
            nms_counters_deleted=nms_counters_deleted,
            syslog_messages_deleted=syslog_messages_deleted,
            audit_events_deleted=audit_events_deleted,
            security_audit_events_deleted=security_audit_events_deleted,
            notification_deliveries_deleted=notification_deliveries_deleted,
        )

    def list_hourly(
        self,
        device_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 5000,
    ) -> HourlyMetricSeries:
        bounded_limit = min(max(limit, 1), 5000)
        with self._session_factory() as session:
            rows = session.scalars(
                select(MetricHourlyRollupRow)
                .where(
                    MetricHourlyRollupRow.device_id == device_id,
                    MetricHourlyRollupRow.metric_type == metric_name,
                    MetricHourlyRollupRow.bucket_start >= start,
                    MetricHourlyRollupRow.bucket_start <= end,
                )
                .order_by(MetricHourlyRollupRow.bucket_start.desc(), MetricHourlyRollupRow.id.desc())
                .limit(bounded_limit + 1)
            ).all()

        truncated = len(rows) > bounded_limit
        selected = list(reversed(rows[:bounded_limit]))
        return HourlyMetricSeries(
            device_id=device_id,
            metric_name=metric_name,
            start=start,
            end=end,
            truncated=truncated,
            points=tuple(
                HourlyMetricPoint(
                    timestamp=row.bucket_start,
                    average=row.average,
                    minimum=row.minimum,
                    maximum=row.maximum,
                    samples=row.samples,
                    unit=row.unit,
                )
                for row in selected
            ),
        )
