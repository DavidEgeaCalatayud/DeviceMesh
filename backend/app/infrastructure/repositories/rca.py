from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database import DeviceEventRow, DeviceRow
from app.infrastructure.repositories.platform import (
    ServiceDependencyRow,
    ServiceMonitorRow,
    ServiceRow,
)
from app.infrastructure.repositories.synthetics import (
    ServiceIncidentRow,
    SyntheticMonitorRow,
)
from app.infrastructure.repositories.syslog import SyslogMessageRow


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(slots=True)
class _Candidate:
    kind: str
    entity_id: str
    label: str
    causal_path: list[str]
    score: int = 0
    first_signal_at: datetime | None = None
    evidence: list[dict[str, object]] = field(default_factory=list)

    def add(
        self,
        *,
        kind: str,
        summary: str,
        weight: int,
        timestamp: datetime | None = None,
    ) -> None:
        self.score = min(100, self.score + max(0, weight))
        if timestamp is not None:
            timestamp = _aware(timestamp)
            if self.first_signal_at is None or timestamp < self.first_signal_at:
                self.first_signal_at = timestamp
        self.evidence.append(
            {
                "kind": kind,
                "summary": summary[:512],
                "weight": weight,
                "timestamp": timestamp,
            }
        )

    def view(self) -> dict[str, object]:
        if self.score >= 70:
            confidence = "high"
        elif self.score >= 40:
            confidence = "medium"
        else:
            confidence = "low"
        return {
            "kind": self.kind,
            "entityId": self.entity_id,
            "label": self.label,
            "score": self.score,
            "confidence": confidence,
            "causalPath": self.causal_path,
            "firstSignalAt": self.first_signal_at,
            "evidence": self.evidence[:12],
        }


class RcaRepository:
    """Explainable incident correlation over the explicit DeviceMesh service/device graph."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    @staticmethod
    def _service_paths(
        session: Session,
        impacted_service_ids: list[str],
        max_depth: int = 5,
    ) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {}
        pending: list[tuple[str, list[str], int]] = [
            (service_id, [service_id], 0) for service_id in impacted_service_ids
        ]
        while pending:
            current, path, depth = pending.pop(0)
            existing = paths.get(current)
            if existing is not None and len(existing) <= len(path):
                continue
            paths[current] = path
            if depth >= max_depth:
                continue
            dependencies = session.scalars(
                select(ServiceDependencyRow).where(
                    ServiceDependencyRow.service_id == current
                )
            ).all()
            for dependency in dependencies:
                upstream = dependency.depends_on_service_id
                if upstream in path:
                    continue
                pending.append((upstream, [upstream, *path], depth + 1))
        return paths

    @staticmethod
    def _service_labels(session: Session, service_ids: list[str]) -> dict[str, str]:
        if not service_ids:
            return {}
        rows = session.scalars(
            select(ServiceRow).where(ServiceRow.id.in_(service_ids))
        ).all()
        return {row.id: row.name for row in rows}

    @staticmethod
    def _monitor_ids(session: Session, service_id: str) -> list[str]:
        return list(
            session.scalars(
                select(ServiceMonitorRow.monitor_id).where(
                    ServiceMonitorRow.service_id == service_id
                )
            )
        )

    @staticmethod
    def _device_signals(
        session: Session,
        candidate: _Candidate,
        device_id: str,
        start: datetime,
        end: datetime,
    ) -> None:
        events = session.scalars(
            select(DeviceEventRow)
            .where(
                DeviceEventRow.device_id == device_id,
                DeviceEventRow.timestamp >= start,
                DeviceEventRow.timestamp <= end,
            )
            .order_by(DeviceEventRow.timestamp)
            .limit(8)
        ).all()
        severity_weights = {
            "critical": 18,
            "error": 15,
            "warning": 9,
            "info": 3,
        }
        strongest_event = 0
        for event in events:
            weight = severity_weights.get(event.severity.lower(), 4)
            strongest_event = max(strongest_event, weight)
            candidate.evidence.append(
                {
                    "kind": "device_event",
                    "summary": f"{event.name} on {device_id}"[:512],
                    "weight": weight,
                    "timestamp": _aware(event.timestamp),
                }
            )
            at = _aware(event.timestamp)
            if candidate.first_signal_at is None or at < candidate.first_signal_at:
                candidate.first_signal_at = at
        candidate.score = min(100, candidate.score + strongest_event)

        syslog = session.scalars(
            select(SyslogMessageRow)
            .where(
                SyslogMessageRow.device_id == device_id,
                SyslogMessageRow.received_at >= start,
                SyslogMessageRow.received_at <= end,
            )
            .order_by(SyslogMessageRow.severity, SyslogMessageRow.received_at)
            .limit(8)
        ).all()
        syslog_weights = {0: 18, 1: 17, 2: 16, 3: 14, 4: 8, 5: 4, 6: 2, 7: 1}
        strongest_syslog = 0
        for message in syslog[:4]:
            weight = syslog_weights.get(message.severity, 1)
            strongest_syslog = max(strongest_syslog, weight)
            candidate.evidence.append(
                {
                    "kind": "syslog",
                    "summary": (
                        f"facility={message.facility} severity={message.severity}: "
                        f"{message.message[:240]}"
                    ),
                    "weight": weight,
                    "timestamp": _aware(message.received_at),
                }
            )
            at = _aware(message.received_at)
            if candidate.first_signal_at is None or at < candidate.first_signal_at:
                candidate.first_signal_at = at
        candidate.score = min(100, candidate.score + strongest_syslog)

    def explain(self, incident_id: str) -> dict[str, object]:
        with self.sessions() as session:
            incident = session.get(ServiceIncidentRow, incident_id)
            if incident is None:
                raise LookupError("incident not found")

            target_start = _aware(incident.opened_at)
            evidence_start = target_start - timedelta(minutes=30)
            evidence_end = target_start + timedelta(minutes=10)
            impacted_service_ids = list(
                session.scalars(
                    select(ServiceMonitorRow.service_id).where(
                        ServiceMonitorRow.monitor_id == incident.monitor_id
                    )
                )
            )
            paths = self._service_paths(session, impacted_service_ids)
            labels = self._service_labels(session, list(paths))
            candidates: dict[tuple[str, str], _Candidate] = {}

            for service_id, path in paths.items():
                service = session.get(ServiceRow, service_id)
                if service is None:
                    continue
                distance = max(0, len(path) - 1)
                candidate = _Candidate(
                    kind="service",
                    entity_id=service_id,
                    label=service.name,
                    causal_path=[labels.get(item, item) for item in path],
                )
                base_weight = 15 if distance == 0 else max(20, 50 - (distance - 1) * 9)
                candidate.add(
                    kind="dependency_path",
                    summary=(
                        "Impacted service itself"
                        if distance == 0
                        else "Upstream dependency path: " + " -> ".join(candidate.causal_path)
                    ),
                    weight=base_weight,
                )

                monitor_ids = self._monitor_ids(session, service_id)
                if monitor_ids:
                    related = session.scalars(
                        select(ServiceIncidentRow)
                        .where(
                            ServiceIncidentRow.id != incident.id,
                            ServiceIncidentRow.monitor_id.in_(monitor_ids),
                            ServiceIncidentRow.opened_at >= evidence_start,
                            ServiceIncidentRow.opened_at <= evidence_end,
                        )
                        .order_by(ServiceIncidentRow.opened_at)
                        .limit(4)
                    ).all()
                    for related_incident in related:
                        related_at = _aware(related_incident.opened_at)
                        before_target = related_at <= target_start
                        candidate.add(
                            kind="correlated_incident",
                            summary=(
                                f"{related_incident.classification} on linked monitor "
                                f"{related_incident.monitor_id} "
                                f"{'preceded' if before_target else 'followed'} the incident"
                            ),
                            weight=30 if before_target else 10,
                            timestamp=related_at,
                        )

                if service.device_id:
                    self._device_signals(
                        session,
                        candidate,
                        service.device_id,
                        evidence_start,
                        evidence_end,
                    )

                candidates[(candidate.kind, candidate.entity_id)] = candidate

            monitor = session.get(SyntheticMonitorRow, incident.monitor_id)
            if monitor is not None and monitor.device_id:
                device = session.get(DeviceRow, monitor.device_id)
                label = (device.hostname if device else None) or monitor.device_id
                key = ("device", monitor.device_id)
                device_candidate = candidates.get(key)
                if device_candidate is None:
                    device_candidate = _Candidate(
                        kind="device",
                        entity_id=monitor.device_id,
                        label=label,
                        causal_path=[label],
                    )
                    candidates[key] = device_candidate
                device_candidate.add(
                    kind="monitored_device",
                    summary="Device is directly attached to the failing synthetic monitor",
                    weight=15,
                )
                if incident.host_offline_at_open:
                    device_candidate.add(
                        kind="host_offline",
                        summary="Host was already offline when the incident opened",
                        weight=40,
                        timestamp=target_start,
                    )
                self._device_signals(
                    session,
                    device_candidate,
                    monitor.device_id,
                    evidence_start,
                    evidence_end,
                )

            ordered = sorted(
                candidates.values(),
                key=lambda item: (
                    -item.score,
                    item.first_signal_at or datetime.max.replace(tzinfo=UTC),
                    item.kind,
                    item.entity_id,
                ),
            )
            views = [candidate.view() for candidate in ordered[:10]]
            return {
                "incidentId": incident.id,
                "generatedAt": datetime.now(UTC),
                "method": "dependency-temporal-evidence-v1",
                "status": "explained" if views else "insufficient_data",
                "primaryCandidate": views[0] if views else None,
                "candidates": views,
                "evidenceWindow": {
                    "start": evidence_start,
                    "end": evidence_end,
                },
                "limitations": [
                    "Correlation is evidence, not proof of causation.",
                    "Scores are deterministic heuristics over data already observed by DeviceMesh.",
                    "Missing service links, device events or Syslog reduce confidence rather than implying health.",
                ],
            }
