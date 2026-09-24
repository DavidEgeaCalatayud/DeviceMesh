from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.synthetics.models import (
    SyntheticCheckErrorKind,
    SyntheticCheckResult,
    SyntheticHealthSummary,
    SyntheticMonitor,
    SyntheticMonitorKind,
    SyntheticSlaWindow,
)
from app.infrastructure.database import Base


class SyntheticMonitorRow(Base):
    __tablename__ = "synthetic_monitors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target: Mapped[str] = mapped_column(String(2048), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    http_method: Mapped[str | None] = mapped_column(String(8))
    expected_status: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyntheticCheckResultRow(Base):
    __tablename__ = "synthetic_check_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_kind: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(String(1024))
    probe_id: Mapped[str] = mapped_column(String(128), nullable=False)


class SyntheticMonitorNotFoundError(LookupError):
    pass


def _monitor(row: SyntheticMonitorRow) -> SyntheticMonitor:
    return SyntheticMonitor(
        id=row.id,
        name=row.name,
        kind=SyntheticMonitorKind(row.kind),
        target=row.target,
        port=row.port,
        device_id=row.device_id,
        interval_seconds=row.interval_seconds,
        timeout_seconds=row.timeout_seconds,
        enabled=row.enabled,
        http_method=row.http_method,
        expected_status=row.expected_status,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        next_run_at=row.next_run_at,
    )


def _result(row: SyntheticCheckResultRow) -> SyntheticCheckResult:
    return SyntheticCheckResult(
        id=row.id,
        monitor_id=row.monitor_id,
        checked_at=row.checked_at,
        success=row.success,
        latency_ms=row.latency_ms,
        http_status=row.http_status,
        error_kind=SyntheticCheckErrorKind(row.error_kind) if row.error_kind else None,
        error=row.error,
        probe_id=row.probe_id,
    )


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


class SqlAlchemySyntheticRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_monitor(
        self,
        *,
        name: str,
        kind: SyntheticMonitorKind,
        target: str,
        port: int | None,
        device_id: str | None,
        interval_seconds: int,
        timeout_seconds: float,
        http_method: str | None,
        expected_status: int | None,
        created_by: str = "operator",
        now: datetime | None = None,
    ) -> SyntheticMonitor:
        current = now or datetime.now(UTC)
        row = SyntheticMonitorRow(
            id=str(uuid4()),
            name=name.strip(),
            kind=kind.value,
            target=target.strip(),
            port=port,
            device_id=device_id,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            enabled=True,
            http_method=http_method,
            expected_status=expected_status,
            created_by=created_by,
            created_at=current,
            updated_at=current,
            next_run_at=current,
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _monitor(row)

    def list_monitors(self, *, device_id: str | None = None) -> list[SyntheticMonitor]:
        stmt = select(SyntheticMonitorRow).order_by(SyntheticMonitorRow.name.asc())
        if device_id is not None:
            stmt = stmt.where(SyntheticMonitorRow.device_id == device_id)
        with self._session_factory() as session:
            return [_monitor(row) for row in session.scalars(stmt).all()]

    def get_monitor(self, monitor_id: str) -> SyntheticMonitor:
        with self._session_factory() as session:
            row = session.get(SyntheticMonitorRow, monitor_id)
            if row is None:
                raise SyntheticMonitorNotFoundError(monitor_id)
            return _monitor(row)

    def set_enabled(
        self,
        monitor_id: str,
        enabled: bool,
        *,
        now: datetime | None = None,
    ) -> SyntheticMonitor:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticMonitorRow, monitor_id)
            if row is None:
                raise SyntheticMonitorNotFoundError(monitor_id)
            row.enabled = enabled
            row.updated_at = current
            if enabled:
                row.next_run_at = current
            session.commit()
            session.refresh(row)
            return _monitor(row)

    def claim_due(
        self,
        *,
        now: datetime | None = None,
        limit: int = 10,
    ) -> list[SyntheticMonitor]:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            stmt = (
                select(SyntheticMonitorRow)
                .where(
                    SyntheticMonitorRow.enabled.is_(True),
                    SyntheticMonitorRow.next_run_at <= current,
                )
                .order_by(SyntheticMonitorRow.next_run_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = list(session.scalars(stmt).all())
            for row in rows:
                row.next_run_at = current + timedelta(seconds=row.interval_seconds)
                row.updated_at = current
            session.commit()
            return [_monitor(row) for row in rows]

    def record_result(
        self,
        *,
        monitor_id: str,
        success: bool,
        latency_ms: float,
        http_status: int | None,
        error_kind: SyntheticCheckErrorKind | None,
        error: str | None,
        probe_id: str,
        checked_at: datetime | None = None,
    ) -> SyntheticCheckResult:
        current = checked_at or datetime.now(UTC)
        row = SyntheticCheckResultRow(
            monitor_id=monitor_id,
            checked_at=current,
            success=success,
            latency_ms=max(0.0, latency_ms),
            http_status=http_status,
            error_kind=error_kind.value if error_kind else None,
            error=error[:1024] if error else None,
            probe_id=probe_id[:128],
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _result(row)

    def list_results(self, monitor_id: str, *, limit: int = 100) -> list[SyntheticCheckResult]:
        stmt = (
            select(SyntheticCheckResultRow)
            .where(SyntheticCheckResultRow.monitor_id == monitor_id)
            .order_by(SyntheticCheckResultRow.checked_at.desc())
            .limit(limit)
        )
        with self._session_factory() as session:
            return [_result(row) for row in session.scalars(stmt).all()]

    def summarize(
        self,
        monitor_id: str,
        now: datetime | None = None,
    ) -> SyntheticHealthSummary:
        current = now or datetime.now(UTC)
        windows = (("24h", timedelta(hours=24)), ("7d", timedelta(days=7)), ("30d", timedelta(days=30)))
        summaries: list[SyntheticSlaWindow] = []
        with self._session_factory() as session:
            for label, delta in windows:
                start = current - delta
                stmt = select(SyntheticCheckResultRow).where(
                    SyntheticCheckResultRow.monitor_id == monitor_id,
                    SyntheticCheckResultRow.checked_at >= start,
                    SyntheticCheckResultRow.checked_at <= current,
                )
                rows = list(session.scalars(stmt).all())
                total = len(rows)
                successes = sum(1 for row in rows if row.success)
                latencies = [row.latency_ms for row in rows if row.success]
                summaries.append(
                    SyntheticSlaWindow(
                        label=label,
                        window_start=start,
                        window_end=current,
                        total_checks=total,
                        successful_checks=successes,
                        failed_checks=total - successes,
                        availability_percent=(successes / total * 100.0) if total else None,
                        mean_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
                        p95_latency_ms=_p95(latencies),
                    )
                )

            recent_stmt = (
                select(SyntheticCheckResultRow)
                .where(SyntheticCheckResultRow.monitor_id == monitor_id)
                .order_by(SyntheticCheckResultRow.checked_at.desc())
                .limit(500)
            )
            recent = list(session.scalars(recent_stmt).all())

        consecutive_failures = 0
        failing_since: datetime | None = None
        for row in recent:
            if row.success:
                break
            consecutive_failures += 1
            failing_since = row.checked_at
        return SyntheticHealthSummary(
            monitor_id=monitor_id,
            generated_at=current,
            consecutive_failures=consecutive_failures,
            failing_since=failing_since,
            windows=tuple(summaries),
        )
