from __future__ import annotations

import math
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.synthetics.models import (
    ProbeServiceState,
    ServiceConsensus,
    ServiceConsensusClassification,
)
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticCheckResultRow,
    SyntheticMonitorNotFoundError,
    SyntheticMonitorRow,
    SyntheticProbeAssignmentRow,
    SyntheticProbeRow,
)


class RoundAwareSyntheticRepository(SqlAlchemySyntheticRepository):
    """Synthetic repository with round-aware majority quorum semantics.

    V1 consensus treated the latest result from every recently-seen probe as if
    those observations were simultaneous. V2 only combines observations that
    belong to the same temporal round and requires a strict configurable
    majority of the active assigned probes before classifying service health.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        quorum_ratio: float = 0.5,
        minimum_quorum: int = 1,
        round_window_seconds: int = 30,
        probe_stale_seconds: int = 120,
    ) -> None:
        super().__init__(session_factory)
        if not 0.5 <= quorum_ratio < 1.0:
            raise ValueError("quorum_ratio must be between 0.5 (inclusive) and 1.0")
        if minimum_quorum < 1:
            raise ValueError("minimum_quorum must be positive")
        if round_window_seconds < 1:
            raise ValueError("round_window_seconds must be positive")
        if probe_stale_seconds < 1:
            raise ValueError("probe_stale_seconds must be positive")
        self._quorum_ratio = quorum_ratio
        self._minimum_quorum = minimum_quorum
        self._round_window_seconds = round_window_seconds
        self._probe_stale_seconds = probe_stale_seconds

    def _required_quorum(self, expected_probes: int) -> int:
        if expected_probes <= 0:
            return self._minimum_quorum
        strict_majority = math.floor(expected_probes * self._quorum_ratio) + 1
        return min(expected_probes, max(self._minimum_quorum, strict_majority))

    def _active_probe_ids(
        self,
        session: Session,
        monitor_id: str,
        now: datetime,
    ) -> set[str]:
        active_after = now - timedelta(seconds=self._probe_stale_seconds)
        rows = session.execute(
            select(SyntheticProbeAssignmentRow.probe_id)
            .join(
                SyntheticProbeRow,
                SyntheticProbeRow.id == SyntheticProbeAssignmentRow.probe_id,
            )
            .where(
                SyntheticProbeAssignmentRow.monitor_id == monitor_id,
                SyntheticProbeAssignmentRow.enabled.is_(True),
                SyntheticProbeRow.enabled.is_(True),
                SyntheticProbeRow.last_seen_at.is_not(None),
                SyntheticProbeRow.last_seen_at >= active_after,
            )
        ).scalars()
        return set(rows)

    def _consensus_for_session(
        self,
        session: Session,
        monitor_id: str,
        now: datetime,
    ) -> ServiceConsensus:
        monitor = session.get(SyntheticMonitorRow, monitor_id)
        if monitor is None:
            raise SyntheticMonitorNotFoundError(monitor_id)

        history_cutoff = now - timedelta(seconds=max(180, monitor.interval_seconds * 3))
        rows = list(
            session.scalars(
                select(SyntheticCheckResultRow)
                .where(
                    SyntheticCheckResultRow.monitor_id == monitor_id,
                    SyntheticCheckResultRow.checked_at >= history_cutoff,
                    SyntheticCheckResultRow.checked_at <= now,
                )
                .order_by(SyntheticCheckResultRow.checked_at.desc())
                .limit(1000)
            ).all()
        )
        active_probe_ids = self._active_probe_ids(session, monitor_id, now)

        if not rows:
            return ServiceConsensus(
                monitor_id=monitor_id,
                generated_at=now,
                classification=ServiceConsensusClassification.INSUFFICIENT_DATA,
                healthy_probes=0,
                failing_probes=0,
                states=(),
            )

        # Anchor the round to the newest observation. The window is deliberately
        # shorter than a normal polling interval so results from the previous
        # round cannot satisfy quorum for a newly-started round.
        newest = rows[0].checked_at
        round_window = min(self._round_window_seconds, max(1, monitor.interval_seconds // 2))
        round_start = newest - timedelta(seconds=round_window)

        latest: dict[str, SyntheticCheckResultRow] = {}
        for row in rows:
            if row.checked_at < round_start:
                break
            if active_probe_ids and row.probe_id not in active_probe_ids:
                continue
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
        expected = len(active_probe_ids) if active_probe_ids else len(states)
        required = self._required_quorum(expected)
        healthy = sum(1 for state in states if state.success)
        failing = len(states) - healthy

        if len(states) < required:
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
