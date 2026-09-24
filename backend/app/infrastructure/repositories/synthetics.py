from __future__ import annotations

import hashlib
import math
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    exists,
    or_,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.synthetics.models import (
    ProbeServiceState,
    ServiceConsensus,
    ServiceConsensusClassification,
    ServiceIncident,
    ServiceIncidentClassification,
    ServiceIncidentState,
    ServiceIncidentSummary,
    SyntheticCheckErrorKind,
    SyntheticCheckResult,
    SyntheticHealthSummary,
    SyntheticMonitor,
    SyntheticMonitorKind,
    SyntheticProbe,
    SyntheticProbeAssignment,
    SyntheticProbeRegistration,
    SyntheticSlaWindow,
    SyntheticWorkItem,
)
from app.infrastructure.database import (
    Base,
    DeviceAvailabilityIntervalRow,
    MaintenanceWindowRow,
)


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
    failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    recovery_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
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
    probe_location: Mapped[str | None] = mapped_column(String(128))
    work_id: Mapped[str | None] = mapped_column(String(36), unique=True)


class SyntheticProbeRow(Base):
    __tablename__ = "synthetic_probes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyntheticProbeAssignmentRow(Base):
    __tablename__ = "synthetic_probe_assignments"

    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), primary_key=True
    )
    probe_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_probes.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyntheticProbeWorkRow(Base):
    __tablename__ = "synthetic_probe_work"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), nullable=False
    )
    probe_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_probes.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class ServiceIncidentStateRow(Base):
    __tablename__ = "service_incident_state"

    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), primary_key=True
    )
    failure_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recovery_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_classification: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ServiceIncidentRow(Base):
    __tablename__ = "service_incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    maintenance_active_at_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    host_offline_at_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failing_probes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_probes: Mapped[int] = mapped_column(Integer, nullable=False)


class SyntheticMonitorNotFoundError(LookupError):
    pass


class SyntheticProbeNotFoundError(LookupError):
    pass


class SyntheticProbeAuthenticationError(PermissionError):
    pass


class SyntheticWorkNotFoundError(LookupError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        failure_threshold=row.failure_threshold,
        recovery_threshold=row.recovery_threshold,
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
        probe_location=row.probe_location,
        work_id=row.work_id,
    )


def _probe(row: SyntheticProbeRow) -> SyntheticProbe:
    return SyntheticProbe(
        id=row.id,
        name=row.name,
        location=row.location,
        capabilities=tuple(SyntheticMonitorKind(value) for value in row.capabilities),
        enabled=row.enabled,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _assignment(row: SyntheticProbeAssignmentRow) -> SyntheticProbeAssignment:
    return SyntheticProbeAssignment(
        monitor_id=row.monitor_id,
        probe_id=row.probe_id,
        enabled=row.enabled,
        next_run_at=row.next_run_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _incident(row: ServiceIncidentRow) -> ServiceIncident:
    return ServiceIncident(
        id=row.id,
        monitor_id=row.monitor_id,
        state=ServiceIncidentState(row.state),
        classification=ServiceIncidentClassification(row.classification),
        opened_at=row.opened_at,
        resolved_at=row.resolved_at,
        last_observed_at=row.last_observed_at,
        failure_threshold=row.failure_threshold,
        recovery_threshold=row.recovery_threshold,
        maintenance_active_at_open=row.maintenance_active_at_open,
        host_offline_at_open=row.host_offline_at_open,
        failing_probes=row.failing_probes,
        total_probes=row.total_probes,
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
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
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
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
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
        probe_stale_seconds: int = 120,
    ) -> list[SyntheticMonitor]:
        current = now or datetime.now(UTC)
        active_after = current - timedelta(seconds=probe_stale_seconds)
        active_assignment = exists().where(
            SyntheticProbeAssignmentRow.monitor_id == SyntheticMonitorRow.id,
            SyntheticProbeAssignmentRow.enabled.is_(True),
            SyntheticProbeAssignmentRow.probe_id == SyntheticProbeRow.id,
            SyntheticProbeRow.enabled.is_(True),
            SyntheticProbeRow.last_seen_at.is_not(None),
            SyntheticProbeRow.last_seen_at >= active_after,
        )
        with self._session_factory() as session:
            stmt = (
                select(SyntheticMonitorRow)
                .where(
                    SyntheticMonitorRow.enabled.is_(True),
                    SyntheticMonitorRow.next_run_at <= current,
                    ~active_assignment,
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

    def create_probe(
        self,
        *,
        name: str,
        location: str,
        capabilities: tuple[SyntheticMonitorKind, ...],
        now: datetime | None = None,
    ) -> SyntheticProbeRegistration:
        current = now or datetime.now(UTC)
        unique_capabilities = tuple(sorted(set(capabilities), key=lambda item: item.value))
        if not unique_capabilities:
            raise ValueError("probe requires at least one capability")
        token = secrets.token_urlsafe(32)
        row = SyntheticProbeRow(
            id=str(uuid4()),
            name=name.strip(),
            location=location.strip(),
            capabilities=[item.value for item in unique_capabilities],
            token_hash=_token_hash(token),
            enabled=True,
            last_seen_at=None,
            created_at=current,
            updated_at=current,
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return SyntheticProbeRegistration(probe=_probe(row), token=token)

    def list_probes(self) -> list[SyntheticProbe]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(SyntheticProbeRow).order_by(
                    SyntheticProbeRow.location.asc(),
                    SyntheticProbeRow.name.asc(),
                )
            ).all()
            return [_probe(row) for row in rows]

    def authenticate_probe(self, token: str) -> SyntheticProbe:
        digest = _token_hash(token)
        with self._session_factory() as session:
            row = session.scalar(
                select(SyntheticProbeRow).where(SyntheticProbeRow.token_hash == digest).limit(1)
            )
            if row is None or not row.enabled:
                raise SyntheticProbeAuthenticationError("invalid probe credential")
            return _probe(row)

    def heartbeat_probe(
        self,
        probe_id: str,
        *,
        now: datetime | None = None,
    ) -> SyntheticProbe:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticProbeRow, probe_id)
            if row is None:
                raise SyntheticProbeNotFoundError(probe_id)
            row.last_seen_at = current
            row.updated_at = current
            session.commit()
            session.refresh(row)
            return _probe(row)

    def set_probe_enabled(
        self,
        probe_id: str,
        enabled: bool,
        *,
        now: datetime | None = None,
    ) -> SyntheticProbe:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticProbeRow, probe_id)
            if row is None:
                raise SyntheticProbeNotFoundError(probe_id)
            row.enabled = enabled
            row.updated_at = current
            session.commit()
            session.refresh(row)
            return _probe(row)

    def assign_probe(
        self,
        monitor_id: str,
        probe_id: str,
        *,
        now: datetime | None = None,
    ) -> SyntheticProbeAssignment:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            monitor = session.get(SyntheticMonitorRow, monitor_id)
            if monitor is None:
                raise SyntheticMonitorNotFoundError(monitor_id)
            probe = session.get(SyntheticProbeRow, probe_id)
            if probe is None:
                raise SyntheticProbeNotFoundError(probe_id)
            if monitor.kind not in probe.capabilities:
                raise ValueError("probe does not advertise the monitor capability")
            row = session.get(SyntheticProbeAssignmentRow, (monitor_id, probe_id))
            if row is None:
                row = SyntheticProbeAssignmentRow(
                    monitor_id=monitor_id,
                    probe_id=probe_id,
                    enabled=True,
                    next_run_at=current,
                    created_at=current,
                    updated_at=current,
                )
                session.add(row)
            else:
                row.enabled = True
                row.next_run_at = current
                row.updated_at = current
            session.commit()
            session.refresh(row)
            return _assignment(row)

    def set_assignment_enabled(
        self,
        monitor_id: str,
        probe_id: str,
        enabled: bool,
        *,
        now: datetime | None = None,
    ) -> SyntheticProbeAssignment:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticProbeAssignmentRow, (monitor_id, probe_id))
            if row is None:
                raise SyntheticProbeNotFoundError(probe_id)
            row.enabled = enabled
            row.updated_at = current
            if enabled:
                row.next_run_at = current
            session.commit()
            session.refresh(row)
            return _assignment(row)

    def list_assignments(self, monitor_id: str | None = None) -> list[SyntheticProbeAssignment]:
        stmt = select(SyntheticProbeAssignmentRow)
        if monitor_id is not None:
            stmt = stmt.where(SyntheticProbeAssignmentRow.monitor_id == monitor_id)
        stmt = stmt.order_by(
            SyntheticProbeAssignmentRow.monitor_id.asc(),
            SyntheticProbeAssignmentRow.probe_id.asc(),
        )
        with self._session_factory() as session:
            return [_assignment(row) for row in session.scalars(stmt).all()]

    def claim_probe_work(
        self,
        probe_id: str,
        *,
        now: datetime | None = None,
        limit: int = 10,
        lease_seconds: int = 60,
    ) -> list[SyntheticWorkItem]:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            probe = session.get(SyntheticProbeRow, probe_id)
            if probe is None or not probe.enabled:
                raise SyntheticProbeNotFoundError(probe_id)
            probe.last_seen_at = current
            probe.updated_at = current

            expired = session.scalars(
                select(SyntheticProbeWorkRow).where(
                    SyntheticProbeWorkRow.probe_id == probe_id,
                    SyntheticProbeWorkRow.status == "leased",
                    SyntheticProbeWorkRow.lease_expires_at < current,
                )
            ).all()
            for work in expired:
                work.status = "expired"

            assignments = list(
                session.scalars(
                    select(SyntheticProbeAssignmentRow)
                    .where(
                        SyntheticProbeAssignmentRow.probe_id == probe_id,
                        SyntheticProbeAssignmentRow.enabled.is_(True),
                        SyntheticProbeAssignmentRow.next_run_at <= current,
                    )
                    .order_by(SyntheticProbeAssignmentRow.next_run_at.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                ).all()
            )
            items: list[SyntheticWorkItem] = []
            for assignment in assignments:
                monitor = session.get(SyntheticMonitorRow, assignment.monitor_id)
                if monitor is None or not monitor.enabled or monitor.kind not in probe.capabilities:
                    continue
                work = SyntheticProbeWorkRow(
                    id=str(uuid4()),
                    monitor_id=monitor.id,
                    probe_id=probe_id,
                    assigned_at=current,
                    lease_expires_at=current + timedelta(seconds=lease_seconds),
                    completed_at=None,
                    status="leased",
                )
                session.add(work)
                assignment.next_run_at = current + timedelta(seconds=monitor.interval_seconds)
                assignment.updated_at = current
                items.append(
                    SyntheticWorkItem(
                        id=work.id,
                        probe_id=probe_id,
                        monitor=_monitor(monitor),
                        assigned_at=current,
                        lease_expires_at=work.lease_expires_at,
                    )
                )
            session.commit()
            return items

    def complete_probe_work(
        self,
        *,
        work_id: str,
        probe_id: str,
        success: bool,
        latency_ms: float,
        http_status: int | None,
        error_kind: SyntheticCheckErrorKind | None,
        error: str | None,
        checked_at: datetime | None = None,
    ) -> SyntheticCheckResult:
        current = checked_at or datetime.now(UTC)
        with self._session_factory() as session:
            work = session.get(SyntheticProbeWorkRow, work_id)
            if work is None or work.probe_id != probe_id:
                raise SyntheticWorkNotFoundError(work_id)
            existing = session.scalar(
                select(SyntheticCheckResultRow).where(
                    SyntheticCheckResultRow.work_id == work_id
                )
            )
            if existing is not None:
                return _result(existing)
            probe = session.get(SyntheticProbeRow, probe_id)
            if probe is None:
                raise SyntheticProbeNotFoundError(probe_id)
            result = self._add_result(
                session,
                monitor_id=work.monitor_id,
                success=success,
                latency_ms=latency_ms,
                http_status=http_status,
                error_kind=error_kind,
                error=error,
                probe_id=probe_id,
                probe_location=probe.location,
                work_id=work_id,
                checked_at=current,
            )
            work.status = "completed"
            work.completed_at = current
            probe.last_seen_at = current
            probe.updated_at = current
            self._evaluate_incident(session, work.monitor_id, current)
            session.commit()
            session.refresh(result)
            return _result(result)

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
        probe_location: str | None = None,
        work_id: str | None = None,
        checked_at: datetime | None = None,
    ) -> SyntheticCheckResult:
        current = checked_at or datetime.now(UTC)
        with self._session_factory() as session:
            row = self._add_result(
                session,
                monitor_id=monitor_id,
                success=success,
                latency_ms=latency_ms,
                http_status=http_status,
                error_kind=error_kind,
                error=error,
                probe_id=probe_id,
                probe_location=probe_location,
                work_id=work_id,
                checked_at=current,
            )
            self._evaluate_incident(session, monitor_id, current)
            session.commit()
            session.refresh(row)
            return _result(row)

    @staticmethod
    def _add_result(
        session: Session,
        *,
        monitor_id: str,
        success: bool,
        latency_ms: float,
        http_status: int | None,
        error_kind: SyntheticCheckErrorKind | None,
        error: str | None,
        probe_id: str,
        probe_location: str | None,
        work_id: str | None,
        checked_at: datetime,
    ) -> SyntheticCheckResultRow:
        row = SyntheticCheckResultRow(
            monitor_id=monitor_id,
            checked_at=checked_at,
            success=success,
            latency_ms=max(0.0, latency_ms),
            http_status=http_status,
            error_kind=error_kind.value if error_kind else None,
            error=error[:1024] if error else None,
            probe_id=probe_id[:128],
            probe_location=probe_location[:128] if probe_location else None,
            work_id=work_id,
        )
        session.add(row)
        session.flush()
        return row

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
        windows = (
            ("24h", timedelta(hours=24)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
        )
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

            recent = list(
                session.scalars(
                    select(SyntheticCheckResultRow)
                    .where(SyntheticCheckResultRow.monitor_id == monitor_id)
                    .order_by(SyntheticCheckResultRow.checked_at.desc())
                    .limit(500)
                ).all()
            )

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

    def consensus(
        self,
        monitor_id: str,
        now: datetime | None = None,
    ) -> ServiceConsensus:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            return self._consensus_for_session(session, monitor_id, current)

    def _consensus_for_session(
        self,
        session: Session,
        monitor_id: str,
        now: datetime,
    ) -> ServiceConsensus:
        monitor = session.get(SyntheticMonitorRow, monitor_id)
        if monitor is None:
            raise SyntheticMonitorNotFoundError(monitor_id)
        cutoff = now - timedelta(seconds=max(180, monitor.interval_seconds * 3))
        rows = session.scalars(
            select(SyntheticCheckResultRow)
            .where(
                SyntheticCheckResultRow.monitor_id == monitor_id,
                SyntheticCheckResultRow.checked_at >= cutoff,
                SyntheticCheckResultRow.checked_at <= now,
            )
            .order_by(SyntheticCheckResultRow.checked_at.desc())
            .limit(1000)
        ).all()
        latest: dict[str, SyntheticCheckResultRow] = {}
        for row in rows:
            latest.setdefault(row.probe_id, row)
        states = tuple(
            ProbeServiceState(
                probe_id=row.probe_id,
                location=row.probe_location or row.probe_id,
                success=row.success,
                checked_at=row.checked_at,
                latency_ms=row.latency_ms,
            )
            for row in sorted(latest.values(), key=lambda item: item.probe_id)
        )
        healthy = sum(1 for state in states if state.success)
        failing = len(states) - healthy
        if not states:
            classification = ServiceConsensusClassification.INSUFFICIENT_DATA
        elif failing == 0:
            classification = ServiceConsensusClassification.HEALTHY
        elif healthy == 0:
            classification = ServiceConsensusClassification.GLOBAL_OUTAGE
        else:
            classification = ServiceConsensusClassification.REGIONAL_DEGRADATION
        return ServiceConsensus(
            monitor_id=monitor_id,
            generated_at=now,
            classification=classification,
            healthy_probes=healthy,
            failing_probes=failing,
            states=states,
        )

    def _evaluate_incident(self, session: Session, monitor_id: str, now: datetime) -> None:
        monitor = session.get(SyntheticMonitorRow, monitor_id)
        if monitor is None:
            return
        consensus = self._consensus_for_session(session, monitor_id, now)
        if consensus.classification is ServiceConsensusClassification.INSUFFICIENT_DATA:
            return
        state = session.get(ServiceIncidentStateRow, monitor_id)
        if state is None:
            state = ServiceIncidentStateRow(
                monitor_id=monitor_id,
                failure_streak=0,
                recovery_streak=0,
                last_classification=None,
                updated_at=now,
            )
            session.add(state)
        open_incident = session.scalar(
            select(ServiceIncidentRow)
            .where(
                ServiceIncidentRow.monitor_id == monitor_id,
                ServiceIncidentRow.state == ServiceIncidentState.OPEN.value,
            )
            .order_by(ServiceIncidentRow.opened_at.desc())
            .limit(1)
        )
        unhealthy = consensus.classification in {
            ServiceConsensusClassification.GLOBAL_OUTAGE,
            ServiceConsensusClassification.REGIONAL_DEGRADATION,
        }
        if unhealthy:
            state.failure_streak += 1
            state.recovery_streak = 0
            state.last_classification = consensus.classification.value
            if open_incident is None and state.failure_streak >= monitor.failure_threshold:
                incident_classification = (
                    ServiceIncidentClassification.SERVICE_OUTAGE
                    if consensus.classification is ServiceConsensusClassification.GLOBAL_OUTAGE
                    else ServiceIncidentClassification.REGIONAL_PATH
                )
                open_incident = ServiceIncidentRow(
                    id=str(uuid4()),
                    monitor_id=monitor_id,
                    state=ServiceIncidentState.OPEN.value,
                    classification=incident_classification.value,
                    opened_at=now,
                    resolved_at=None,
                    last_observed_at=now,
                    failure_threshold=monitor.failure_threshold,
                    recovery_threshold=monitor.recovery_threshold,
                    maintenance_active_at_open=self._maintenance_active(session, monitor, now),
                    host_offline_at_open=self._host_offline(session, monitor),
                    failing_probes=consensus.failing_probes,
                    total_probes=len(consensus.states),
                )
                session.add(open_incident)
            elif open_incident is not None:
                open_incident.classification = (
                    ServiceIncidentClassification.SERVICE_OUTAGE.value
                    if consensus.classification is ServiceConsensusClassification.GLOBAL_OUTAGE
                    else ServiceIncidentClassification.REGIONAL_PATH.value
                )
                open_incident.last_observed_at = now
                open_incident.failing_probes = consensus.failing_probes
                open_incident.total_probes = len(consensus.states)
        else:
            state.failure_streak = 0
            state.recovery_streak += 1
            state.last_classification = consensus.classification.value
            if open_incident is not None:
                open_incident.last_observed_at = now
                if state.recovery_streak >= monitor.recovery_threshold:
                    open_incident.state = ServiceIncidentState.RESOLVED.value
                    open_incident.resolved_at = now
        state.updated_at = now

    @staticmethod
    def _maintenance_active(
        session: Session,
        monitor: SyntheticMonitorRow,
        now: datetime,
    ) -> bool:
        device_filter = MaintenanceWindowRow.device_id.is_(None)
        if monitor.device_id is not None:
            device_filter = or_(
                MaintenanceWindowRow.device_id.is_(None),
                MaintenanceWindowRow.device_id == monitor.device_id,
            )
        return (
            session.scalar(
                select(MaintenanceWindowRow.id)
                .where(
                    device_filter,
                    MaintenanceWindowRow.cancelled_at.is_(None),
                    MaintenanceWindowRow.starts_at <= now,
                    MaintenanceWindowRow.ends_at > now,
                )
                .limit(1)
            )
            is not None
        )

    @staticmethod
    def _host_offline(session: Session, monitor: SyntheticMonitorRow) -> bool:
        if monitor.device_id is None:
            return False
        current = session.scalar(
            select(DeviceAvailabilityIntervalRow)
            .where(
                DeviceAvailabilityIntervalRow.device_id == monitor.device_id,
                DeviceAvailabilityIntervalRow.ended_at.is_(None),
            )
            .order_by(DeviceAvailabilityIntervalRow.started_at.desc())
            .limit(1)
        )
        return current is not None and current.state == "offline"

    def incidents(
        self,
        monitor_id: str,
        *,
        limit: int = 100,
        now: datetime | None = None,
    ) -> ServiceIncidentSummary:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            rows = list(
                session.scalars(
                    select(ServiceIncidentRow)
                    .where(ServiceIncidentRow.monitor_id == monitor_id)
                    .order_by(ServiceIncidentRow.opened_at.desc())
                    .limit(min(max(limit, 1), 500))
                ).all()
            )
        incidents = tuple(_incident(row) for row in rows)
        open_incident = next(
            (item for item in incidents if item.state is ServiceIncidentState.OPEN),
            None,
        )
        resolved = [
            item.duration_seconds(current)
            for item in incidents
            if item.state is ServiceIncidentState.RESOLVED and item.resolved_at is not None
        ]
        return ServiceIncidentSummary(
            monitor_id=monitor_id,
            open_incident=open_incident,
            incidents=incidents,
            resolved_count=len(resolved),
            mean_recovery_seconds=sum(resolved) / len(resolved) if resolved else None,
        )
