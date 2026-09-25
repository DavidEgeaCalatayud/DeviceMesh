"""Service catalogue, dependency graph, incident workflow and SLO reporting."""
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


class ServiceGroupRow(Base):
    __tablename__ = "service_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(String(2048), default="")
    owner: Mapped[str] = mapped_column(String(128), default="")
    environment: Mapped[str] = mapped_column(String(64), default="production")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ServiceGroupMemberRow(Base):
    __tablename__ = "service_group_members"
    group_id: Mapped[str] = mapped_column(ForeignKey("service_groups.id", ondelete="CASCADE"), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"), primary_key=True)


class ServiceDependencyRow(Base):
    __tablename__ = "service_dependencies"
    service_id: Mapped[str] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"), primary_key=True)
    depends_on_service_id: Mapped[str] = mapped_column(ForeignKey("service_catalog.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="hard")


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
    impact_summary: Mapped[str] = mapped_column(String(10000), default="")
    postmortem: Mapped[str] = mapped_column(String(20000), default="")
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
    sli_mode: Mapped[str] = mapped_column(String(16), default="checks")


def timeline(session: Session, incident_id: str, actor: str, action: str,
             details: dict[str, object] | None = None, now: datetime | None = None) -> None:
    session.add(IncidentTimelineRow(id=str(uuid4()), incident_id=incident_id,
                                   actor=actor, action=action, details=details or {},
                                   timestamp=now or datetime.now(UTC)))


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class PlatformRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    @staticmethod
    def service_view(session: Session, row: ServiceRow) -> dict[str, object]:
        monitors = list(session.scalars(select(ServiceMonitorRow.monitor_id).where(
            ServiceMonitorRow.service_id == row.id)))
        groups = list(session.scalars(select(ServiceGroupMemberRow.group_id).where(
            ServiceGroupMemberRow.service_id == row.id)))
        dependencies = [{"serviceId": dependency.depends_on_service_id, "kind": dependency.kind}
                        for dependency in session.scalars(select(ServiceDependencyRow).where(
                            ServiceDependencyRow.service_id == row.id))]
        dependents = [{"serviceId": dependency.service_id, "kind": dependency.kind}
                      for dependency in session.scalars(select(ServiceDependencyRow).where(
                          ServiceDependencyRow.depends_on_service_id == row.id))]
        return {"id": row.id, "name": row.name, "description": row.description,
                "owner": row.owner, "environment": row.environment, "criticality": row.criticality,
                "tags": row.tags, "deviceId": row.device_id, "monitorIds": monitors,
                "groupIds": groups, "dependencies": dependencies, "dependents": dependents,
                "createdAt": row.created_at}

    @staticmethod
    def group_view(session: Session, row: ServiceGroupRow) -> dict[str, object]:
        services = list(session.scalars(select(ServiceGroupMemberRow.service_id).where(
            ServiceGroupMemberRow.group_id == row.id)))
        return {"id": row.id, "name": row.name, "description": row.description,
                "owner": row.owner, "environment": row.environment, "tags": row.tags,
                "serviceIds": services, "createdAt": row.created_at}

    def create_service(self, data: dict[str, object], actor: str) -> dict[str, object]:
        data = dict(data)
        with self.sessions.begin() as session:
            device_id = data.pop("deviceId", None)
            if device_id and not session.get(DeviceRow, device_id):
                raise LookupError("device not found")
            row = ServiceRow(id=str(uuid4()), created_at=datetime.now(UTC), device_id=device_id, **data)
            session.add(row)
            session.flush()
            audit(session, actor, "service.created", row.id)
            return self.service_view(session, row)

    def update_service(self, service_id: str, data: dict[str, object], actor: str) -> dict[str, object]:
        with self.sessions.begin() as session:
            row = session.get(ServiceRow, service_id)
            if not row:
                raise LookupError("service not found")
            if "deviceId" in data:
                device_id = data.pop("deviceId")
                if device_id and not session.get(DeviceRow, device_id):
                    raise LookupError("device not found")
                row.device_id = device_id
            fields = {"name", "description", "owner", "environment", "criticality", "tags"}
            for key, value in data.items():
                if key in fields:
                    setattr(row, key, value)
            audit(session, actor, "service.updated", row.id, {"fields": sorted(data)})
            session.flush()
            return self.service_view(session, row)

    def list_services(self, limit: int, offset: int, search: str) -> list[dict[str, object]]:
        with self.sessions() as session:
            query = select(ServiceRow).order_by(ServiceRow.name, ServiceRow.id).limit(limit).offset(offset)
            if search:
                query = query.where(ServiceRow.name.icontains(search, autoescape=True))
            return [self.service_view(session, row) for row in session.scalars(query)]

    def create_group(self, data: dict[str, object], actor: str) -> dict[str, object]:
        with self.sessions.begin() as session:
            row = ServiceGroupRow(id=str(uuid4()), created_at=datetime.now(UTC), **data)
            session.add(row)
            session.flush()
            audit(session, actor, "service_group.created", row.id)
            return self.group_view(session, row)

    def list_groups(self, limit: int, offset: int) -> list[dict[str, object]]:
        with self.sessions() as session:
            query = select(ServiceGroupRow).order_by(ServiceGroupRow.name, ServiceGroupRow.id).limit(limit).offset(offset)
            return [self.group_view(session, row) for row in session.scalars(query)]

    def set_group_membership(self, group_id: str, service_id: str, enabled: bool, actor: str) -> None:
        with self.sessions.begin() as session:
            if not session.get(ServiceGroupRow, group_id) or not session.get(ServiceRow, service_id):
                raise LookupError("service group or service not found")
            row = session.get(ServiceGroupMemberRow, (group_id, service_id))
            if enabled and not row:
                session.add(ServiceGroupMemberRow(group_id=group_id, service_id=service_id))
            elif not enabled and row:
                session.delete(row)
            audit(session, actor, "service_group.membership_changed", group_id,
                  {"serviceId": service_id, "enabled": enabled})

    def link_monitor(self, service_id: str, monitor_id: str, actor: str) -> None:
        with self.sessions.begin() as session:
            if not session.get(ServiceRow, service_id) or not session.get(SyntheticMonitorRow, monitor_id):
                raise LookupError("service or monitor not found")
            if not session.get(ServiceMonitorRow, (service_id, monitor_id)):
                session.add(ServiceMonitorRow(service_id=service_id, monitor_id=monitor_id))
                audit(session, actor, "service.monitor_linked", service_id, {"monitorId": monitor_id})

    @staticmethod
    def _dependency_reaches(session: Session, start: str, target: str) -> bool:
        pending = [start]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(session.scalars(select(ServiceDependencyRow.depends_on_service_id).where(
                ServiceDependencyRow.service_id == current)))
        return False

    def set_dependency(self, service_id: str, dependency_id: str, kind: str, actor: str) -> None:
        with self.sessions.begin() as session:
            if service_id == dependency_id:
                raise ValueError("a service cannot depend on itself")
            if not session.get(ServiceRow, service_id) or not session.get(ServiceRow, dependency_id):
                raise LookupError("service not found")
            if self._dependency_reaches(session, dependency_id, service_id):
                raise ValueError("service dependency would create a cycle")
            row = session.get(ServiceDependencyRow, (service_id, dependency_id))
            if row:
                row.kind = kind
            else:
                session.add(ServiceDependencyRow(service_id=service_id, depends_on_service_id=dependency_id, kind=kind))
            audit(session, actor, "service.dependency_set", service_id,
                  {"dependsOn": dependency_id, "kind": kind})

    def remove_dependency(self, service_id: str, dependency_id: str, actor: str) -> None:
        with self.sessions.begin() as session:
            row = session.get(ServiceDependencyRow, (service_id, dependency_id))
            if not row:
                raise LookupError("service dependency not found")
            session.delete(row)
            audit(session, actor, "service.dependency_removed", service_id, {"dependsOn": dependency_id})

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
                "impactSummary": workflow.impact_summary if workflow else "",
                "postmortem": workflow.postmortem if workflow else "",
                "tags": workflow.tags if workflow else []}

    def list_incidents(self, limit: int, offset: int, active_only: bool) -> list[dict[str, object]]:
        with self.sessions() as session:
            query = select(ServiceIncidentRow).order_by(ServiceIncidentRow.opened_at.desc(), ServiceIncidentRow.id)
            if active_only:
                query = query.where(ServiceIncidentRow.state == "open")
            return [self.incident_view(session, row) for row in session.scalars(query.limit(limit).offset(offset))]

    @staticmethod
    def _correlated_incidents(session: Session, incident: ServiceIncidentRow) -> list[dict[str, object]]:
        direct_services = set(session.scalars(select(ServiceMonitorRow.service_id).where(
            ServiceMonitorRow.monitor_id == incident.monitor_id)))
        if not direct_services:
            return []
        related_services = set(direct_services)
        related_services.update(session.scalars(select(ServiceDependencyRow.depends_on_service_id).where(
            ServiceDependencyRow.service_id.in_(direct_services))))
        related_services.update(session.scalars(select(ServiceDependencyRow.service_id).where(
            ServiceDependencyRow.depends_on_service_id.in_(direct_services))))
        monitor_ids = set(session.scalars(select(ServiceMonitorRow.monitor_id).where(
            ServiceMonitorRow.service_id.in_(related_services))))
        start = _aware(incident.opened_at) or datetime.now(UTC)
        end = _aware(incident.resolved_at) or datetime.now(UTC)
        margin = timedelta(minutes=15)
        candidates = session.scalars(select(ServiceIncidentRow).where(
            ServiceIncidentRow.monitor_id.in_(monitor_ids), ServiceIncidentRow.id != incident.id
        ).order_by(ServiceIncidentRow.opened_at)).all()
        result: list[dict[str, object]] = []
        for candidate in candidates:
            candidate_start = _aware(candidate.opened_at) or start
            candidate_end = _aware(candidate.resolved_at) or datetime.now(UTC)
            if candidate_start <= end + margin and candidate_end >= start - margin:
                result.append({"id": candidate.id, "monitorId": candidate.monitor_id,
                               "classification": candidate.classification, "state": candidate.state,
                               "openedAt": candidate.opened_at, "resolvedAt": candidate.resolved_at})
            if len(result) >= 50:
                break
        return result

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
            result["correlatedIncidents"] = self._correlated_incidents(session, row)
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
                                                  status=row.state, root_cause="", resolution="",
                                                  impact_summary="", postmortem="", tags=[])
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
                      "resolution": "resolution", "impactSummary": "impact_summary",
                      "postmortem": "postmortem", "tags": "tags"}
            for key, value in changes.items():
                if key in fields:
                    setattr(workflow, fields[key], value)
            if changes.get("note"):
                timeline(session, incident_id, actor, "note.added", {"note": changes["note"]})
            if "postmortem" in changes:
                timeline(session, incident_id, actor, "postmortem.updated")
            delta = {key: value for key, value in changes.items() if key not in {"note", "postmortem"}}
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
                         name=data["name"], target_percent=data["targetPercent"],
                         window_days=data["windowDays"], sli_mode=data.get("sliMode", "checks"))
            session.add(row)
            audit(session, actor, "slo.created", row.id, {"sliMode": row.sli_mode})
            return row.id

    @staticmethod
    def _time_stats(session: Session, monitor: SyntheticMonitorRow, start: datetime,
                    end: datetime) -> tuple[float, float, int, int]:
        checks = list(session.scalars(select(SyntheticCheckResultRow).where(
            SyntheticCheckResultRow.monitor_id == monitor.id,
            SyntheticCheckResultRow.checked_at > start,
            SyntheticCheckResultRow.checked_at <= end,
        ).order_by(SyntheticCheckResultRow.checked_at)))
        previous = session.scalar(select(SyntheticCheckResultRow).where(
            SyntheticCheckResultRow.monitor_id == monitor.id,
            SyntheticCheckResultRow.checked_at <= start,
        ).order_by(SyntheticCheckResultRow.checked_at.desc()).limit(1))
        if previous is not None:
            previous_at = _aware(previous.checked_at)
            if previous_at and previous_at >= start - timedelta(seconds=monitor.interval_seconds * 2):
                checks.insert(0, previous)
        observed = 0.0
        failed = 0.0
        total_checks = 0
        bad_checks = 0
        for index, check in enumerate(checks):
            checked_at = max(_aware(check.checked_at) or start, start)
            if checked_at >= end:
                continue
            natural_end = checked_at + timedelta(seconds=monitor.interval_seconds * 2)
            next_at = _aware(checks[index + 1].checked_at) if index + 1 < len(checks) else end
            segment_end = min(end, natural_end, next_at or end)
            seconds = max(0.0, (segment_end - checked_at).total_seconds())
            if seconds:
                observed += seconds
                if not check.success:
                    failed += seconds
            if _aware(check.checked_at) and _aware(check.checked_at) >= start:
                total_checks += 1
                bad_checks += 0 if check.success else 1
        return observed, failed, total_checks, bad_checks

    @staticmethod
    def _check_stats(session: Session, monitor_id: str, start: datetime,
                     end: datetime) -> tuple[float, float, int, int]:
        total = session.scalar(select(func.count()).select_from(SyntheticCheckResultRow).where(
            SyntheticCheckResultRow.monitor_id == monitor_id,
            SyntheticCheckResultRow.checked_at >= start,
            SyntheticCheckResultRow.checked_at <= end)) or 0
        bad = session.scalar(select(func.count()).select_from(SyntheticCheckResultRow).where(
            SyntheticCheckResultRow.monitor_id == monitor_id,
            SyntheticCheckResultRow.checked_at >= start,
            SyntheticCheckResultRow.checked_at <= end,
            SyntheticCheckResultRow.success.is_(False))) or 0
        return float(total), float(bad), int(total), int(bad)

    def slo_reports(self, service_id: str) -> list[dict[str, object]]:
        now = datetime.now(UTC)
        with self.sessions() as session:
            if not session.get(ServiceRow, service_id):
                raise LookupError("service not found")
            reports = []
            for slo in session.scalars(select(SloRow).where(SloRow.service_id == service_id)):
                monitor = session.get(SyntheticMonitorRow, slo.monitor_id)
                if not monitor:
                    continue
                stats: dict[str, tuple[float, float, int, int]] = {}
                windows = (("window", timedelta(days=slo.window_days)), ("1h", timedelta(hours=1)),
                           ("6h", timedelta(hours=6)), ("24h", timedelta(hours=24)))
                for label, delta in windows:
                    if slo.sli_mode == "time":
                        stats[label] = self._time_stats(session, monitor, now - delta, now)
                    else:
                        stats[label] = self._check_stats(session, slo.monitor_id, now - delta, now)
                total_units, bad_units, total_checks, bad_checks = stats["window"]
                last_check = session.scalar(select(func.max(SyntheticCheckResultRow.checked_at)).where(
                    SyntheticCheckResultRow.monitor_id == slo.monitor_id,
                    SyntheticCheckResultRow.checked_at <= now))
                last_check = _aware(last_check)
                fresh = bool(monitor.enabled and last_check is not None
                             and last_check >= now - timedelta(seconds=monitor.interval_seconds * 2))
                allowed_fraction = 1 - slo.target_percent / 100
                budget = total_units * allowed_fraction
                burn_rates = {label: (failed / observed / allowed_fraction if observed else None)
                              for label, (observed, failed, _, _) in stats.items() if label != "window"}
                one_hour, six_hour, day = burn_rates.get("1h"), burn_rates.get("6h"), burn_rates.get("24h")
                if not fresh or total_units <= 0:
                    burn_alert = "unknown"
                elif one_hour is not None and six_hour is not None and one_hour >= 14.4 and six_hour >= 6:
                    burn_alert = "critical"
                elif (six_hour is not None and six_hour >= 6) or (day is not None and day >= 3):
                    burn_alert = "warning"
                else:
                    burn_alert = "normal"
                window_seconds = timedelta(days=slo.window_days).total_seconds()
                reports.append({
                    "id": slo.id, "name": slo.name, "monitorId": slo.monitor_id,
                    "sli": "time_availability" if slo.sli_mode == "time" else "check_success_ratio",
                    "sliMode": slo.sli_mode, "windowDays": slo.window_days,
                    "targetPercent": slo.target_percent, "totalChecks": total_checks,
                    "failedChecks": bad_checks,
                    "actualPercent": 100 * (1 - bad_units / total_units) if total_units else None,
                    "budgetUnit": "seconds" if slo.sli_mode == "time" else "checks",
                    "allowedBadUnits": budget, "remainingBadUnits": budget - bad_units if total_units else None,
                    "allowedFailedChecks": budget if slo.sli_mode == "checks" else None,
                    "remainingFailedChecks": budget - bad_units if total_units and slo.sli_mode == "checks" else None,
                    "observedSeconds": total_units if slo.sli_mode == "time" else None,
                    "failedSeconds": bad_units if slo.sli_mode == "time" else None,
                    "coveragePercent": min(100.0, 100 * total_units / window_seconds) if slo.sli_mode == "time" else None,
                    "status": "unknown" if not total_units or not fresh else ("met" if bad_units <= budget else "breached"),
                    "lastCheckedAt": last_check, "dataState": "fresh" if fresh else "stale",
                    "burnRates": burn_rates,
                    "burnAlert": burn_alert,
                    "burnPolicy": {"critical": "1h>=14.4x and 6h>=6x", "warning": "6h>=6x or 24h>=3x"},
                    "generatedAt": now,
                })
            return reports
