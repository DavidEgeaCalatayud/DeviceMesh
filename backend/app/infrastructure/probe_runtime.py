from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.database import Base, SessionFactory
from app.infrastructure.repositories.synthetics import SyntheticProbeRow


class ProbeCredentialLifecycleRow(Base):
    __tablename__ = "synthetic_probe_credentials"

    probe_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_probes.id", ondelete="CASCADE"), primary_key=True
    )
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProbeRuntimeRow(Base):
    __tablename__ = "synthetic_probe_runtime"

    probe_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_probes.id", ondelete="CASCADE"), primary_key=True
    )
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    uptime_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_checks: Mapped[int] = mapped_column(Integer, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True, slots=True)
class ProbeRuntimeSnapshot:
    probe_id: str
    credential_rotated_at: datetime
    credential_expires_at: datetime
    agent_version: str | None
    uptime_seconds: int | None
    queue_depth: int | None
    queue_capacity: int | None
    max_concurrent_checks: int | None
    reported_at: datetime | None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def credential_expired(token: str, *, now: datetime | None = None) -> bool:
    """Return True only for a known probe whose lifecycle credential is expired/missing."""
    current = now or datetime.now(UTC)
    digest = _token_hash(token)
    with SessionFactory() as session:
        row = session.execute(
            select(SyntheticProbeRow.id, ProbeCredentialLifecycleRow.expires_at)
            .outerjoin(
                ProbeCredentialLifecycleRow,
                ProbeCredentialLifecycleRow.probe_id == SyntheticProbeRow.id,
            )
            .where(SyntheticProbeRow.token_hash == digest)
            .limit(1)
        ).first()
        if row is None:
            # Unknown credentials are rejected by the existing probe authenticator.
            return False
        expires_at = row[1]
        return expires_at is None or _aware(expires_at) <= current


class ProbeRuntimeService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def record(
        self,
        probe_id: str,
        *,
        agent_version: str,
        uptime_seconds: int,
        queue_depth: int,
        queue_capacity: int,
        max_concurrent_checks: int,
        now: datetime | None = None,
    ) -> ProbeRuntimeSnapshot:
        current = now or datetime.now(UTC)
        with self.sessions.begin() as session:
            row = session.get(ProbeRuntimeRow, probe_id)
            if row is None:
                row = ProbeRuntimeRow(
                    probe_id=probe_id,
                    agent_version=agent_version,
                    uptime_seconds=uptime_seconds,
                    queue_depth=queue_depth,
                    queue_capacity=queue_capacity,
                    max_concurrent_checks=max_concurrent_checks,
                    reported_at=current,
                )
                session.add(row)
            else:
                row.agent_version = agent_version
                row.uptime_seconds = uptime_seconds
                row.queue_depth = queue_depth
                row.queue_capacity = queue_capacity
                row.max_concurrent_checks = max_concurrent_checks
                row.reported_at = current
        return self.get(probe_id)

    def get(self, probe_id: str) -> ProbeRuntimeSnapshot:
        with self.sessions() as session:
            lifecycle = session.get(ProbeCredentialLifecycleRow, probe_id)
            if lifecycle is None:
                raise LookupError("probe credential lifecycle not found")
            runtime = session.get(ProbeRuntimeRow, probe_id)
            return ProbeRuntimeSnapshot(
                probe_id=probe_id,
                credential_rotated_at=lifecycle.rotated_at,
                credential_expires_at=lifecycle.expires_at,
                agent_version=runtime.agent_version if runtime else None,
                uptime_seconds=runtime.uptime_seconds if runtime else None,
                queue_depth=runtime.queue_depth if runtime else None,
                queue_capacity=runtime.queue_capacity if runtime else None,
                max_concurrent_checks=runtime.max_concurrent_checks if runtime else None,
                reported_at=runtime.reported_at if runtime else None,
            )
