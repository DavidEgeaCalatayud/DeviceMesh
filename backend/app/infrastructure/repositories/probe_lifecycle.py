from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.synthetics.models import SyntheticMonitorKind, SyntheticProbeRegistration
from app.infrastructure.database import Base
from app.infrastructure.repositories.synthetic_consensus import RoundAwareSyntheticRepository
from app.infrastructure.repositories.synthetics import (
    SyntheticProbeAuthenticationError,
    SyntheticProbeRow,
)


class SyntheticProbeLifecycleRow(Base):
    __tablename__ = "synthetic_probe_lifecycle"

    probe_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_probes.id", ondelete="CASCADE"), primary_key=True
    )
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_version: Mapped[str | None] = mapped_column(String(64))
    uptime_seconds: Mapped[int | None] = mapped_column(BigInteger)
    outbox_depth: Mapped[int | None] = mapped_column(Integer)
    failed_requests_total: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(String(512))
    telemetry_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@dataclass(frozen=True, slots=True)
class ProbeLifecycleSnapshot:
    probe_id: str
    token_expires_at: datetime
    agent_version: str | None
    uptime_seconds: int | None
    outbox_depth: int | None
    failed_requests_total: int | None
    last_error: str | None
    telemetry_updated_at: datetime | None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _snapshot(row: SyntheticProbeLifecycleRow) -> ProbeLifecycleSnapshot:
    return ProbeLifecycleSnapshot(
        probe_id=row.probe_id,
        token_expires_at=_aware(row.token_expires_at),
        agent_version=row.agent_version,
        uptime_seconds=row.uptime_seconds,
        outbox_depth=row.outbox_depth,
        failed_requests_total=row.failed_requests_total,
        last_error=row.last_error,
        telemetry_updated_at=(
            _aware(row.telemetry_updated_at) if row.telemetry_updated_at is not None else None
        ),
    )


class ProbeLifecycleRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def ensure_credential_lifecycle(
        self,
        probe_id: str,
        *,
        now: datetime,
        ttl_days: int,
    ) -> ProbeLifecycleSnapshot:
        expires_at = now + timedelta(days=ttl_days)
        with self._session_factory.begin() as session:
            row = session.get(SyntheticProbeLifecycleRow, probe_id)
            if row is None:
                row = SyntheticProbeLifecycleRow(
                    probe_id=probe_id,
                    token_expires_at=expires_at,
                )
                session.add(row)
            else:
                row.token_expires_at = expires_at
            session.flush()
            return _snapshot(row)

    def credential_expiry(self, probe_id: str) -> datetime:
        with self._session_factory() as session:
            row = session.get(SyntheticProbeLifecycleRow, probe_id)
            if row is None:
                raise SyntheticProbeAuthenticationError("probe credential lifecycle missing")
            return _aware(row.token_expires_at)

    def require_valid_credential(self, probe_id: str, *, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        if self.credential_expiry(probe_id) <= current:
            raise SyntheticProbeAuthenticationError("probe credential expired")

    def record_telemetry(
        self,
        probe_id: str,
        *,
        agent_version: str,
        uptime_seconds: int,
        outbox_depth: int,
        failed_requests_total: int,
        last_error: str | None,
        now: datetime | None = None,
    ) -> ProbeLifecycleSnapshot:
        current = now or datetime.now(UTC)
        with self._session_factory.begin() as session:
            if session.get(SyntheticProbeRow, probe_id) is None:
                raise LookupError("probe not found")
            row = session.get(SyntheticProbeLifecycleRow, probe_id)
            if row is None:
                raise SyntheticProbeAuthenticationError("probe credential lifecycle missing")
            row.agent_version = agent_version
            row.uptime_seconds = uptime_seconds
            row.outbox_depth = outbox_depth
            row.failed_requests_total = failed_requests_total
            row.last_error = last_error
            row.telemetry_updated_at = current
            session.flush()
            return _snapshot(row)

    def list_snapshots(self) -> list[ProbeLifecycleSnapshot]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(SyntheticProbeLifecycleRow).order_by(SyntheticProbeLifecycleRow.probe_id)
            ).all()
            return [_snapshot(row) for row in rows]


class LifecycleSyntheticRepository(RoundAwareSyntheticRepository):
    """Round-aware synthetics plus finite distributed-probe credentials."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        credential_ttl_days: int,
        quorum_ratio: float = 0.5,
        minimum_quorum: int = 1,
        round_window_seconds: int = 30,
        probe_stale_seconds: int = 120,
    ) -> None:
        super().__init__(
            session_factory,
            quorum_ratio=quorum_ratio,
            minimum_quorum=minimum_quorum,
            round_window_seconds=round_window_seconds,
            probe_stale_seconds=probe_stale_seconds,
        )
        self._lifecycle = ProbeLifecycleRepository(session_factory)
        self._credential_ttl_days = credential_ttl_days

    def create_probe(
        self,
        *,
        name: str,
        location: str,
        capabilities: tuple[SyntheticMonitorKind, ...],
        now: datetime | None = None,
    ) -> SyntheticProbeRegistration:
        current = now or datetime.now(UTC)
        registration = super().create_probe(
            name=name,
            location=location,
            capabilities=capabilities,
            now=current,
        )
        self._lifecycle.ensure_credential_lifecycle(
            registration.probe.id,
            now=current,
            ttl_days=self._credential_ttl_days,
        )
        return registration

    def authenticate_probe(self, token: str, *, now: datetime | None = None):  # type: ignore[no-untyped-def]
        probe = super().authenticate_probe(token)
        self._lifecycle.require_valid_credential(probe.id, now=now)
        return probe
