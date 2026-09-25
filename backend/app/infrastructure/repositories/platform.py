"""Service catalogue, human incident workflow and explicitly check-based SLOs."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.database import Base, DeviceRow
from app.infrastructure.repositories.synthetics import (
    ServiceIncidentRow,
    SyntheticCheckResultRow,
    SyntheticMonitorRow,
)
from app.infrastructure.security.human_auth import audit


class ServiceRow(Base):
    __tablename__ = "service_catalog"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    owner: Mapped[str] = mapped_column(String(128), default="")
    environment: Mapped[str] = mapped_column(String(64), default="production")
    criticality: Mapped[str] = mapped_column(String(16), default="medium")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ServiceMonitorRow(Base):
    __tablename__ = "service_monitors"
    service_id: Mapped[str] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"), primary_key=True)
    monitor_id: Mapped[str] = mapped_column(ForeignKey("synthetic_monitors.id", ondelete="CASCADE"), primary_key=True)


class IncidentManagementRow(Base):
    __tablename__ = "incident_management"
    incident_id: Mapped[str] = mapped_column(ForeignKey("service_incidents.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    severity: Mapped[str] = mapped_column(String(8), default="SEV2")
    status: Mapped[str] = mapped_column(String(24), default="open")
    assigned_to: Mapped[str | None] = mapped_column(String(128))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(128))
    root_cause: Mapped[str] = mapped_column(String(10000), default="")
    resolution: Mapped[str] = mapped_column(String(10000), default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)


class IncidentTimelineRow(Base):
    __tablename__ = "incident_timeline"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("service_incidents.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class SloRow(Base):
    __tablename__ = "service_slos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[str] = mapped_column(ForeignKey("synthetic_monitors.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    target_percent: Mapped[float] = mapped_column(Float)
    window_days: Mapped[int] = mapped_column(Integer)


def timeline(session: Session, incident_id: str, actor: str, action: str,
             details: dict[str, object] | None = None, now: datetime | None = None) -> None:
    session.add(IncidentTimelineRow(id=str(uuid4()), incident_id=incident_id,
                                   actor=actor, action=action, details=details or {},
                                   timestamp=now or datetime.now(UTC)))


class PlatformRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    @staticmethod
    def service_view(session: Session, row: ServiceRow) -> dict[str, object]:
        monitors = list(session.scalars(select(ServiceMonitorRow.monitor_id).where(
            ServiceMonitorRow.service_id == row.id)))
        return {"id": row.id, "name": row.name, "description": row.description,
                "owner": row.owner, "environment": row.environment, "criticality": row.criticality,
                "tags": row.tags, "deviceId": row.device_id, "monitorIds": monitors,
                "createdAt": row.created_at}

    def create_service(self, data: dict[str, object], actor: str) -> dict[str, object]:
        with self.sessions.begin() as session:
            device_id = data.pop("deviceId", None)
            if device_id and not session.get(DeviceRow, device_id):
                raise LookupError("device not found")
            row = ServiceRow(id=str(uuid4()), created_at=datetime.now(UTC), device_id=device_id, **data)
            session.add(row)
            session.flush()
            audit(session, actor, "service.created", row.id)
            return self.service_view(session, row)

    def list_services(self, limit: int, offset: int, search: str) -> list[dict[str, object]]:
        with self.sessions() as session:
            query = select(ServiceRow).order_by(ServiceRow.name, ServiceRow.id).limit(limit).offset(offset)
            if search:
                query = query.where(ServiceRow.name.icontains(search, autoescape=True))
            return [self.service_view(session, row) for row in session.scalars(query)]

    def link_monitor(self, service_id: str, monitor_id: str, actor: str) -> None:
        with self.sessions.begin() as session:
            if not session.get(ServiceRow, service_id) or not session.get(SyntheticMonitorRow, monitor_id):
                raise LookupError("service or monitor not found")
            if not session.get(ServiceMonitorRow, (service_id, monitor_id)):
                session.add(ServiceMonitorRow(service_id=service_id, monitor_id=monitor_id))
                audit(session, actor, "service.monitor_linked", service_id, {"monitorId": monitor_id})

    @staticmethod
    def incident_view(session: Session, row: ServiceIncidentRow) -> dict[str, object]:
        workflow = session.get(IncidentManagementRow, row.id)
        monitor = session.get(SyntheticMonitorRow, row.monitor_id)
        service_ids = list(session.scalars(select(ServiceMonitorRow.service_id).where(
            ServiceMonitorRow.monitor_id == row.monitor_id)))
        phase = "resolved" if row.state == "resolved" else (workflow.status if workflow else "open")
        return {"id": row.id, "monitorId": row.monitor_id, "serviceIds": service_ids,
                "deviceId": monitor.device_id if monitor else None,
                "title": workflow.title if workflow and workflow.title else f"{monitor.name if monitor else row.monitor_id} unavailable",
                "severity": workflow.severity if workflow else "SEV2", "status": phase,
                "classification": row.classification, "openedAt": row.opened_at,
                "resolvedAt": row.resolved_at, "assignedTo": workflow.assigned_to if workflow else None,
                "acknowledgedAt": workflow.acknowledged_at if workflow else None,
                "acknowledgedBy": workflow.acknowledged_by if workflow else None,
                "rootCause": workflow.root_cause if workflow else "",
                "resolution": workflow.resolution if workflow else "",
                "tags": workflow.tags if workflow else []}

    def list_incidents(self, limit: int, offset: int, active_only: bool) -> list[dict[str, object]]:
        with self.sessions() as session:
            query = select(ServiceIncidentRow).order_by(ServiceIncidentRow.opened_at.desc(), ServiceIncidentRow.id)
            if active_only:
                query = query.where(ServiceIncidentRow.state == "open")
            return [self.incident_view(session, row) for row in session.scalars(query.limit(limit).offset(offset))]

    def incident_detail(self, incident_id: str) -> dict[str, object]:
        with self.sessions() as session:
            row = session.get(ServiceIncidentRow, incident_id)
            if not row:
                raise LookupError("incident not found")
            result = self.incident_view(session, row)
            result["timeline"] = [{"id": event.id, "actor": event.actor, "action": event.action,
                                   "timestamp": event.timestamp, "details": event.details}
                                  for event in session.scalars(select(IncidentTimelineRow).where(
                                      IncidentTimelineRow.incident_id == incident_id
                                  ).order_by(IncidentTimelineRow.timestamp, IncidentTimelineRow.id).limit(1000))]
            return result

    def update_incident(self, incident_id: str, changes: dict[str, object], actor: str) -> dict[str, object]:
        transitions = {"open": {"acknowledged", "investigating", "resolved"},
                       "acknowledged": {"investigating", "mitigated", "resolved"},
                       "investigating": {"mitigated", "resolved"},
                       "mitigated": {"investigating", "resolved"}, "resolved": {"open"}}
        with self.sessions.begin() as session:
            monitor_id = session.scalar(select(ServiceIncidentRow.monitor_id).where(
                ServiceIncidentRow.id == incident_id))
            if monitor_id:
                session.scalar(select(SyntheticMonitorRow).where(
                    SyntheticMonitorRow.id == monitor_id).with_for_update())
            row = session.scalar(select(ServiceIncidentRow).where(
                ServiceIncidentRow.id == incident_id).with_for_update())
            if not row:
                raise LookupError("incident not found")
            workflow = session.get(IncidentManagementRow, incident_id)
            if not workflow:
                workflow = IncidentManagementRow(incident_id=incident_id, title="", severity="SEV2",
                                                  status=row.state, root_cause="", resolution="", tags=[])
                session.add(workflow)
            current = "resolved" if row.state == "resolved" else workflow.status
            target = changes.get("status")
            if target and target != current:
                if target not in transitions[current]:
                    raise ValueError(f"cannot transition from {current} to {target}")
                if target == "resolved":
                    if not changes.get("resolution", workflow.resolution):
                        raise ValueError("manual resolution requires a resolution note")
                    row.state, row.resolved_at = "resolved", datetime.now(UTC)
                elif current == "resolved":
                    # Serialize reopen against automatic evaluation on this monitor.
                    session.scalar(select(SyntheticMonitorRow).where(
                        SyntheticMonitorRow.id == row.monitor_id).with_for_update())
                    other = session.scalar(select(ServiceIncidentRow.id).where(
                        ServiceIncidentRow.monitor_id == row.monitor_id,
                        ServiceIncidentRow.state == "open", ServiceIncidentRow.id != row.id))
                    if other:
                        raise ValueError("another incident is already open for this monitor")
                    row.state, row.resolved_at = "open", None
                if target == "acknowledged":
                    workflow.acknowledged_at, workflow.acknowledged_by = datetime.now(UTC), actor
            fields = {"title": "title", "severity": "severity", "status": "status",
                      "assignedTo": "assigned_to", "rootCause": "root_cause",
                      "resolution": "resolution", "tags": "tags"}
            for key, value in changes.items():
                if key in fields:
                    setattr(workflow, fields[key], value)
            if changes.get("note"):
                timeline(session, incident_id, actor, "note.added", {"note": changes["note"]})
            delta = {key: value for key, value in changes.items() if key != "note"}
            if delta:
                timeline(session, incident_id, actor, "incident.updated", delta)
            audit(session, actor, "incident.updated", incident_id, {"fields": list(changes)})
            session.flush()
            return self.incident_view(session, row)

    def create_slo(self, service_id: str, data: dict[str, object], actor: str) -> str:
        with self.sessions.begin() as session:
            monitor_id = data["monitorId"]
            if not session.get(ServiceMonitorRow, (service_id, monitor_id)):
                raise LookupError("monitor must be linked to the service")
            row = SloRow(id=str(uuid4()), service_id=service_id, monitor_id=monitor_id,
                         name=data["name"], target_percent=data["targetPercent"], window_days=data["windowDays"])
            session.add(row)
            audit(session, actor, "slo.created", row.id)
            return row.id

    def slo_reports(self, service_id: str) -> list[dict[str, object]]:
        now = datetime.now(UTC)
        with self.sessions() as session:
            if not session.get(ServiceRow, service_id):
                raise LookupError("service not found")
            reports = []
            for slo in session.scalars(select(SloRow).where(SloRow.service_id == service_id)):
                counts: dict[str, tuple[int, int]] = {}
                for label, delta in (("window", timedelta(days=slo.window_days)),
                                     ("1h", timedelta(hours=1)), ("6h", timedelta(hours=6))):
                    total = session.scalar(select(func.count()).select_from(SyntheticCheckResultRow).where(
                        SyntheticCheckResultRow.monitor_id == slo.monitor_id,
                        SyntheticCheckResultRow.checked_at >= now - delta,
                        SyntheticCheckResultRow.checked_at <= now)) or 0
                    bad = session.scalar(select(func.count()).select_from(SyntheticCheckResultRow).where(
                        SyntheticCheckResultRow.monitor_id == slo.monitor_id,
                        SyntheticCheckResultRow.checked_at >= now - delta,
                        SyntheticCheckResultRow.checked_at <= now,
                        SyntheticCheckResultRow.success.is_(False))) or 0
                    counts[label] = total, bad
                total, bad = counts["window"]
                monitor = session.get(SyntheticMonitorRow, slo.monitor_id)
                last_check = session.scalar(select(func.max(SyntheticCheckResultRow.checked_at)).where(
                    SyntheticCheckResultRow.monitor_id == slo.monitor_id,
                    SyntheticCheckResultRow.checked_at <= now))
                if last_check is not None and last_check.tzinfo is None:
                    last_check = last_check.replace(tzinfo=UTC)
                fresh = bool(monitor and monitor.enabled and last_check is not None
                             and last_check >= now - timedelta(seconds=monitor.interval_seconds * 2))
                allowed_fraction = 1 - slo.target_percent / 100
                budget = total * allowed_fraction
                reports.append({"id": slo.id, "name": slo.name, "monitorId": slo.monitor_id,
                                "sli": "check_success_ratio", "windowDays": slo.window_days,
                                "targetPercent": slo.target_percent, "totalChecks": total,
                                "failedChecks": bad, "actualPercent": 100 * (1 - bad / total) if total else None,
                                "allowedFailedChecks": budget, "remainingFailedChecks": budget - bad if total else None,
                                "status": "unknown" if not total or not fresh else ("met" if bad <= budget else "breached"),
                                "lastCheckedAt": last_check, "dataState": "fresh" if fresh else "stale",
                                "burnRates": {label: (fail / count / allowed_fraction if count else None)
                                              for label, (count, fail) in counts.items() if label != "window"},
                                "generatedAt": now})
            return reports
