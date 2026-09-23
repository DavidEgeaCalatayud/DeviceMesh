from dataclasses import dataclass
from datetime import datetime

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

from app.infrastructure.database import Base, MetricSampleRow


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

            session.flush()
            deletion = session.execute(delete(MetricSampleRow).where(MetricSampleRow.timestamp < cutoff))
            raw_samples_deleted = int(deletion.rowcount or 0)
            session.commit()

        return TelemetryCompactionResult(
            cutoff=cutoff,
            rollups_touched=len(aggregates),
            raw_samples_deleted=raw_samples_deleted,
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
