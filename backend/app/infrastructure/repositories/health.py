from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.health.models import (
    AvailabilityInterval,
    AvailabilityState,
    DeviceHealthSummary,
    MaintenanceWindow,
    SlaWindowSummary,
)
from app.infrastructure.database import (
    DeviceAvailabilityIntervalRow,
    DeviceRow,
    MaintenanceWindowRow,
    SecurityAuditEventRow,
)


class MaintenanceWindowNotFoundError(Exception):
    pass


class SqlAlchemyHealthRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record_state(
        self,
        device_id: str,
        state: AvailabilityState,
        timestamp: datetime,
        source: str,
    ) -> AvailabilityInterval:
        with self._session_factory() as session:
            current = session.scalar(
                select(DeviceAvailabilityIntervalRow)
                .where(
                    DeviceAvailabilityIntervalRow.device_id == device_id,
                    DeviceAvailabilityIntervalRow.ended_at.is_(None),
                )
                .order_by(DeviceAvailabilityIntervalRow.started_at.desc())
                .limit(1)
            )
            if current is not None:
                if current.state == state.value or timestamp <= current.started_at:
                    return self._to_interval(current)
                current.ended_at = timestamp

            row = DeviceAvailabilityIntervalRow(
                device_id=device_id,
                state=state.value,
                started_at=timestamp,
                source=source,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_interval(row)

    def list_intervals(
        self,
        device_id: str,
        start: datetime,
        end: datetime,
    ) -> list[AvailabilityInterval]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(DeviceAvailabilityIntervalRow)
                .where(
                    DeviceAvailabilityIntervalRow.device_id == device_id,
                    DeviceAvailabilityIntervalRow.started_at < end,
                    or_(
                        DeviceAvailabilityIntervalRow.ended_at.is_(None),
                        DeviceAvailabilityIntervalRow.ended_at > start,
                    ),
                )
                .order_by(DeviceAvailabilityIntervalRow.started_at)
            ).all()
            return [self._to_interval(row) for row in rows]

    def list_outages(
        self,
        device_id: str,
        start: datetime,
        end: datetime,
        *,
        limit: int = 100,
    ) -> list[AvailabilityInterval]:
        bounded_limit = min(max(limit, 1), 500)
        with self._session_factory() as session:
            rows = session.scalars(
                select(DeviceAvailabilityIntervalRow)
                .where(
                    DeviceAvailabilityIntervalRow.device_id == device_id,
                    DeviceAvailabilityIntervalRow.state == AvailabilityState.OFFLINE.value,
                    DeviceAvailabilityIntervalRow.started_at < end,
                    or_(
                        DeviceAvailabilityIntervalRow.ended_at.is_(None),
                        DeviceAvailabilityIntervalRow.ended_at > start,
                    ),
                )
                .order_by(DeviceAvailabilityIntervalRow.started_at.desc())
                .limit(bounded_limit)
            ).all()
            return [self._to_interval(row) for row in rows]

    def summarize(
        self,
        device_id: str,
        now: datetime | None = None,
    ) -> DeviceHealthSummary:
        generated_at = now or datetime.now(UTC)
        oldest_start = generated_at - timedelta(days=30)
        intervals = self.list_intervals(device_id, oldest_start, generated_at)
        windows = tuple(
            self._summarize_window(label, generated_at - duration, generated_at, intervals)
            for label, duration in (
                ("24h", timedelta(hours=24)),
                ("7d", timedelta(days=7)),
                ("30d", timedelta(days=30)),
            )
        )
        current = next((interval for interval in reversed(intervals) if interval.ended_at is None), None)
        current_outage_seconds = 0.0
        if current is not None and current.state is AvailabilityState.OFFLINE:
            current_outage_seconds = current.duration_seconds(generated_at)
        return DeviceHealthSummary(
            device_id=device_id,
            generated_at=generated_at,
            current_state=current.state if current is not None else None,
            current_outage_seconds=current_outage_seconds,
            windows=windows,
        )

    @staticmethod
    def _summarize_window(
        label: str,
        start: datetime,
        end: datetime,
        intervals: list[AvailabilityInterval],
    ) -> SlaWindowSummary:
        online_seconds = 0.0
        downtime_seconds = 0.0
        outage_count = 0
        longest_outage_seconds = 0.0
        recovered_durations: list[float] = []

        for interval in intervals:
            interval_end = interval.ended_at or end
            clipped_start = max(start, interval.started_at)
            clipped_end = min(end, interval_end)
            if clipped_end <= clipped_start:
                continue
            duration = (clipped_end - clipped_start).total_seconds()
            if interval.state is AvailabilityState.ONLINE:
                online_seconds += duration
                continue

            downtime_seconds += duration
            outage_count += 1
            longest_outage_seconds = max(longest_outage_seconds, duration)
            if interval.ended_at is not None and start < interval.ended_at <= end:
                recovered_durations.append(
                    max(0.0, (interval.ended_at - interval.started_at).total_seconds())
                )

        monitored_seconds = online_seconds + downtime_seconds
        availability = (
            (online_seconds / monitored_seconds) * 100.0 if monitored_seconds > 0 else None
        )
        mean_recovery = (
            sum(recovered_durations) / len(recovered_durations)
            if recovered_durations
            else None
        )
        return SlaWindowSummary(
            label=label,
            window_start=start,
            window_end=end,
            monitored_seconds=monitored_seconds,
            online_seconds=online_seconds,
            downtime_seconds=downtime_seconds,
            availability_percent=availability,
            outage_count=outage_count,
            longest_outage_seconds=longest_outage_seconds,
            mean_recovery_seconds=mean_recovery,
        )

    @staticmethod
    def _to_interval(row: DeviceAvailabilityIntervalRow) -> AvailabilityInterval:
        return AvailabilityInterval(
            id=row.id,
            device_id=row.device_id,
            state=AvailabilityState(row.state),
            started_at=row.started_at,
            ended_at=row.ended_at,
            source=row.source,
        )


class SqlAlchemyMaintenanceRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(
        self,
        *,
        device_id: str | None,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        created_by: str = "operator",
        created_at: datetime | None = None,
    ) -> MaintenanceWindow:
        if ends_at <= starts_at:
            raise ValueError("maintenance window must end after it starts")
        if ends_at - starts_at > timedelta(days=30):
            raise ValueError("maintenance window cannot exceed 30 days")
        current = created_at or datetime.now(UTC)
        with self._session_factory() as session:
            if device_id is not None and session.get(DeviceRow, device_id) is None:
                raise ValueError("unknown device")
            row = MaintenanceWindowRow(
                device_id=device_id,
                starts_at=starts_at,
                ends_at=ends_at,
                reason=reason.strip(),
                created_by=created_by,
                created_at=current,
            )
            session.add(row)
            session.flush()
            self._audit(
                session,
                "MAINTENANCE_WINDOW_CREATED",
                current,
                {
                    "windowId": row.id,
                    "deviceId": device_id,
                    "startsAt": starts_at.isoformat(),
                    "endsAt": ends_at.isoformat(),
                    "reason": reason.strip(),
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_window(row)

    def cancel(self, window_id: int, now: datetime | None = None) -> MaintenanceWindow:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(MaintenanceWindowRow, window_id)
            if row is None:
                raise MaintenanceWindowNotFoundError
            if row.cancelled_at is None:
                row.cancelled_at = current
                self._audit(
                    session,
                    "MAINTENANCE_WINDOW_CANCELLED",
                    current,
                    {"windowId": row.id, "deviceId": row.device_id},
                )
                session.commit()
                session.refresh(row)
            return self._to_window(row)

    def list_windows(
        self,
        *,
        device_id: str | None = None,
        active_only: bool = False,
        at: datetime | None = None,
        limit: int = 200,
    ) -> list[MaintenanceWindow]:
        timestamp = at or datetime.now(UTC)
        statement = select(MaintenanceWindowRow)
        if device_id is not None:
            statement = statement.where(
                or_(
                    MaintenanceWindowRow.device_id == device_id,
                    MaintenanceWindowRow.device_id.is_(None),
                )
            )
        if active_only:
            statement = statement.where(
                MaintenanceWindowRow.cancelled_at.is_(None),
                MaintenanceWindowRow.starts_at <= timestamp,
                MaintenanceWindowRow.ends_at > timestamp,
            )
        statement = statement.order_by(MaintenanceWindowRow.starts_at.desc()).limit(
            min(max(limit, 1), 500)
        )
        with self._session_factory() as session:
            rows = session.scalars(statement).all()
            return [self._to_window(row) for row in rows]

    def active_window(
        self,
        device_id: str,
        timestamp: datetime,
    ) -> MaintenanceWindow | None:
        windows = self.list_windows(
            device_id=device_id,
            active_only=True,
            at=timestamp,
            limit=20,
        )
        if not windows:
            return None
        specific = next((window for window in windows if window.device_id == device_id), None)
        return specific or windows[0]

    @staticmethod
    def _audit(
        session: Session,
        event_type: str,
        occurred_at: datetime,
        attributes: dict[str, object],
    ) -> None:
        session.add(
            SecurityAuditEventRow(
                event_type=event_type,
                occurred_at=occurred_at,
                attributes=attributes,
            )
        )

    @staticmethod
    def _to_window(row: MaintenanceWindowRow) -> MaintenanceWindow:
        return MaintenanceWindow(
            id=row.id,
            device_id=row.device_id,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            reason=row.reason,
            created_by=row.created_by,
            created_at=row.created_at,
            cancelled_at=row.cancelled_at,
        )
