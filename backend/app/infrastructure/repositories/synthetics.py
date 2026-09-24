from __future__ import annotations

import ipaddress
import math
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.synthetics.models import (
    SyntheticHealthSummary,
    SyntheticMonitor,
    SyntheticMonitorType,
    SyntheticOutage,
    SyntheticProbeResult,
    SyntheticSlaWindow,
    SyntheticState,
)
from app.domain.synthetics.observations import SyntheticProbeObservation
from app.infrastructure.database import DeviceRow, SecurityAuditEventRow
from app.infrastructure.synthetic_database import SyntheticMonitorRow, SyntheticProbeResultRow

_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class SyntheticMonitorNotFoundError(Exception):
    pass


class SyntheticMonitorValidationError(ValueError):
    pass


def _validate_host(value: str) -> str:
    host = value.strip()
    if host != value or not host or len(host) > 253 or host.startswith("-"):
        raise SyntheticMonitorValidationError("synthetic target host is invalid")
    candidate = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        ipaddress.ip_address(candidate)
        return host
    except ValueError:
        labels = host.rstrip(".").split(".")
        if not labels or any(not _HOST_LABEL.fullmatch(label) for label in labels):
            raise SyntheticMonitorValidationError("synthetic target host is invalid") from None
        return host.rstrip(".").lower()


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    return ordered[min(rank - 1, len(ordered) - 1)]


class SqlAlchemySyntheticRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_monitor(
        self,
        *,
        device_id: str,
        name: str,
        monitor_type: SyntheticMonitorType,
        target: str,
        port: int | None = None,
        expected_status_min: int | None = None,
        expected_status_max: int | None = None,
        interval_seconds: int = 60,
        timeout_seconds: int = 5,
        created_by: str = "operator",
        now: datetime | None = None,
    ) -> SyntheticMonitor:
        normalized = self._validate_definition(
            name=name,
            monitor_type=monitor_type,
            target=target,
            port=port,
            expected_status_min=expected_status_min,
            expected_status_max=expected_status_max,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
        )
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            if session.get(DeviceRow, device_id) is None:
                raise SyntheticMonitorValidationError("unknown device")
            row = SyntheticMonitorRow(
                id=str(uuid4()),
                device_id=device_id,
                name=normalized[0],
                monitor_type=monitor_type.value,
                target=normalized[1],
                port=normalized[2],
                expected_status_min=normalized[3],
                expected_status_max=normalized[4],
                interval_seconds=interval_seconds,
                timeout_seconds=timeout_seconds,
                enabled=True,
                created_by=created_by,
                created_at=current,
                updated_at=current,
            )
            session.add(row)
            self._audit(
                session,
                "SYNTHETIC_MONITOR_CREATED",
                current,
                {
                    "monitorId": row.id,
                    "deviceId": device_id,
                    "monitorType": monitor_type.value,
                    "target": row.target,
                    "port": row.port,
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_monitor(row)

    def update_monitor(
        self,
        monitor_id: str,
        *,
        name: str,
        monitor_type: SyntheticMonitorType,
        target: str,
        port: int | None,
        expected_status_min: int | None,
        expected_status_max: int | None,
        interval_seconds: int,
        timeout_seconds: int,
        enabled: bool,
        now: datetime | None = None,
    ) -> SyntheticMonitor:
        normalized = self._validate_definition(
            name=name,
            monitor_type=monitor_type,
            target=target,
            port=port,
            expected_status_min=expected_status_min,
            expected_status_max=expected_status_max,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
        )
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticMonitorRow, monitor_id)
            if row is None:
                raise SyntheticMonitorNotFoundError
            row.name = normalized[0]
            row.monitor_type = monitor_type.value
            row.target = normalized[1]
            row.port = normalized[2]
            row.expected_status_min = normalized[3]
            row.expected_status_max = normalized[4]
            row.interval_seconds = interval_seconds
            row.timeout_seconds = timeout_seconds
            row.enabled = enabled
            row.updated_at = current
            self._audit(
                session,
                "SYNTHETIC_MONITOR_UPDATED",
                current,
                {
                    "monitorId": row.id,
                    "deviceId": row.device_id,
                    "enabled": enabled,
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_monitor(row)

    def disable_monitor(
        self,
        monitor_id: str,
        now: datetime | None = None,
    ) -> SyntheticMonitor:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(SyntheticMonitorRow, monitor_id)
            if row is None:
                raise SyntheticMonitorNotFoundError
            if row.enabled:
                row.enabled = False
                row.updated_at = current
                self._audit(
                    session,
                    "SYNTHETIC_MONITOR_DISABLED",
                    current,
                    {"monitorId": row.id, "deviceId": row.device_id},
                )
                session.commit()
                session.refresh(row)
            return self._to_monitor(row)

    def get_monitor(self, monitor_id: str) -> SyntheticMonitor:
        with self._session_factory() as session:
            row = session.get(SyntheticMonitorRow, monitor_id)
            if row is None:
                raise SyntheticMonitorNotFoundError
            return self._to_monitor(row)

    def list_monitors(
        self,
        *,
        device_id: str | None = None,
        enabled_only: bool = False,
        limit: int = 500,
    ) -> list[SyntheticMonitor]:
        statement = select(SyntheticMonitorRow)
        if device_id is not None:
            statement = statement.where(SyntheticMonitorRow.device_id == device_id)
        if enabled_only:
            statement = statement.where(SyntheticMonitorRow.enabled.is_(True))
        statement = statement.order_by(SyntheticMonitorRow.created_at.desc()).limit(
            min(max(limit, 1), 500)
        )
        with self._session_factory() as session:
            rows = session.scalars(statement).all()
            return [self._to_monitor(row) for row in rows]

    def record_batch(
        self,
        probe_id: str,
        observations: list[SyntheticProbeObservation],
    ) -> list[SyntheticProbeResult]:
        normalized_probe_id = probe_id.strip()
        if not normalized_probe_id or len(normalized_probe_id) > 128:
            raise SyntheticMonitorValidationError("probe id is invalid")
        if len(observations) > 1000:
            raise SyntheticMonitorValidationError("synthetic result batch cannot exceed 1000")

        with self._session_factory() as session:
            monitor_ids = {observation.monitor_id for observation in observations}
            existing_ids = set(
                session.scalars(
                    select(SyntheticMonitorRow.id).where(SyntheticMonitorRow.id.in_(monitor_ids))
                ).all()
            )
            missing = monitor_ids - existing_ids
            if missing:
                raise SyntheticMonitorNotFoundError(next(iter(sorted(missing))))

            rows: list[SyntheticProbeResultRow] = []
            for observation in observations:
                self._validate_observation(observation)
                row = SyntheticProbeResultRow(
                    monitor_id=observation.monitor_id,
                    probe_id=normalized_probe_id,
                    observed_at=observation.observed_at,
                    success=observation.success,
                    latency_ms=observation.latency_ms,
                    http_status=observation.http_status,
                    failure_reason=(
                        observation.failure_reason[:512]
                        if observation.failure_reason is not None
                        else None
                    ),
                    attributes=observation.attributes,
                )
                session.add(row)
                rows.append(row)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [self._to_result(row) for row in rows]

    def list_results(
        self,
        monitor_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[SyntheticProbeResult]:
        statement = select(SyntheticProbeResultRow).where(
            SyntheticProbeResultRow.monitor_id == monitor_id
        )
        if start is not None:
            statement = statement.where(SyntheticProbeResultRow.observed_at >= start)
        if end is not None:
            statement = statement.where(SyntheticProbeResultRow.observed_at <= end)
        statement = statement.order_by(SyntheticProbeResultRow.observed_at.desc()).limit(
            min(max(limit, 1), 2000)
        )
        with self._session_factory() as session:
            rows = session.scalars(statement).all()
            return [self._to_result(row) for row in rows]

    def summarize(
        self,
        monitor_id: str,
        now: datetime | None = None,
    ) -> SyntheticHealthSummary:
        monitor = self.get_monitor(monitor_id)
        generated_at = now or datetime.now(UTC)
        oldest_start = generated_at - timedelta(days=30)
        results = self._results_for_period(monitor_id, oldest_start, generated_at)
        latest = self._latest_result(monitor_id, generated_at)
        current_state = SyntheticState.UNKNOWN
        current_outage_seconds = 0.0
        stale = True
        if latest is not None:
            current_state = SyntheticState.UP if latest.success else SyntheticState.DOWN
            stale = latest.observed_at + self._coverage(monitor) < generated_at
            if not latest.success:
                start = self._current_outage_start(monitor_id, latest.observed_at)
                current_outage_seconds = max(
                    0.0,
                    (generated_at - start).total_seconds(),
                )

        windows = tuple(
            self._summarize_window(
                monitor,
                label,
                generated_at - duration,
                generated_at,
                results,
            )
            for label, duration in (
                ("24h", timedelta(hours=24)),
                ("7d", timedelta(days=7)),
                ("30d", timedelta(days=30)),
            )
        )
        return SyntheticHealthSummary(
            monitor=monitor,
            generated_at=generated_at,
            current_state=current_state,
            current_outage_seconds=current_outage_seconds,
            stale=stale,
            last_observed_at=latest.observed_at if latest is not None else None,
            latest_latency_ms=latest.latency_ms if latest is not None else None,
            latest_http_status=latest.http_status if latest is not None else None,
            latest_failure_reason=latest.failure_reason if latest is not None else None,
            windows=windows,
        )

    def list_outages(
        self,
        monitor_id: str,
        *,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> list[SyntheticOutage]:
        results = self._results_for_period(monitor_id, start, end)
        if not results:
            return []

        outages: list[SyntheticOutage] = []
        outage_start: datetime | None = None
        last_failure_reason: str | None = None
        previous = results[0]
        if not previous.success:
            outage_start = self._current_outage_start(monitor_id, previous.observed_at)
            last_failure_reason = previous.failure_reason

        for result in results[1:]:
            if not result.success:
                if outage_start is None:
                    outage_start = result.observed_at
                last_failure_reason = result.failure_reason
                continue
            if outage_start is not None:
                outages.append(
                    SyntheticOutage(
                        started_at=outage_start,
                        ended_at=result.observed_at,
                        active=False,
                        duration_seconds=max(
                            0.0,
                            (result.observed_at - outage_start).total_seconds(),
                        ),
                        last_failure_reason=last_failure_reason,
                    )
                )
                outage_start = None
                last_failure_reason = None

        if outage_start is not None:
            outages.append(
                SyntheticOutage(
                    started_at=outage_start,
                    ended_at=None,
                    active=True,
                    duration_seconds=max(0.0, (end - outage_start).total_seconds()),
                    last_failure_reason=last_failure_reason,
                )
            )
        return list(reversed(outages[-min(max(limit, 1), 500) :]))

    def _results_for_period(
        self,
        monitor_id: str,
        start: datetime,
        end: datetime,
    ) -> list[SyntheticProbeResult]:
        with self._session_factory() as session:
            previous = session.scalar(
                select(SyntheticProbeResultRow)
                .where(
                    SyntheticProbeResultRow.monitor_id == monitor_id,
                    SyntheticProbeResultRow.observed_at < start,
                )
                .order_by(SyntheticProbeResultRow.observed_at.desc())
                .limit(1)
            )
            rows = session.scalars(
                select(SyntheticProbeResultRow)
                .where(
                    SyntheticProbeResultRow.monitor_id == monitor_id,
                    SyntheticProbeResultRow.observed_at >= start,
                    SyntheticProbeResultRow.observed_at <= end,
                )
                .order_by(SyntheticProbeResultRow.observed_at)
            ).all()
            combined = ([previous] if previous is not None else []) + list(rows)
            return [self._to_result(row) for row in combined]

    def _latest_result(
        self,
        monitor_id: str,
        now: datetime,
    ) -> SyntheticProbeResult | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(SyntheticProbeResultRow)
                .where(
                    SyntheticProbeResultRow.monitor_id == monitor_id,
                    SyntheticProbeResultRow.observed_at <= now,
                )
                .order_by(SyntheticProbeResultRow.observed_at.desc())
                .limit(1)
            )
            return self._to_result(row) if row is not None else None

    def _current_outage_start(self, monitor_id: str, failure_at: datetime) -> datetime:
        with self._session_factory() as session:
            last_success = session.scalar(
                select(func.max(SyntheticProbeResultRow.observed_at)).where(
                    SyntheticProbeResultRow.monitor_id == monitor_id,
                    SyntheticProbeResultRow.success.is_(True),
                    SyntheticProbeResultRow.observed_at < failure_at,
                )
            )
            statement = select(func.min(SyntheticProbeResultRow.observed_at)).where(
                SyntheticProbeResultRow.monitor_id == monitor_id,
                SyntheticProbeResultRow.success.is_(False),
                SyntheticProbeResultRow.observed_at <= failure_at,
            )
            if last_success is not None:
                statement = statement.where(SyntheticProbeResultRow.observed_at > last_success)
            first_failure = session.scalar(statement)
            return first_failure or failure_at

    @classmethod
    def _summarize_window(
        cls,
        monitor: SyntheticMonitor,
        label: str,
        start: datetime,
        end: datetime,
        results: list[SyntheticProbeResult],
    ) -> SyntheticSlaWindow:
        relevant = [result for result in results if result.observed_at < end]
        monitored_seconds = 0.0
        up_seconds = 0.0
        downtime_seconds = 0.0
        coverage = cls._coverage(monitor)

        for index, result in enumerate(relevant):
            segment_start = max(start, result.observed_at)
            next_observed = (
                relevant[index + 1].observed_at if index + 1 < len(relevant) else end
            )
            segment_end = min(end, next_observed, result.observed_at + coverage)
            if segment_end <= segment_start:
                continue
            duration = (segment_end - segment_start).total_seconds()
            monitored_seconds += duration
            if result.success:
                up_seconds += duration
            else:
                downtime_seconds += duration

        latency_values = [
            result.latency_ms
            for result in relevant
            if result.success
            and result.latency_ms is not None
            and start <= result.observed_at <= end
        ]
        outages = cls._window_outages(start, end, relevant)
        longest_outage = max(
            (outage.duration_seconds for outage in outages),
            default=0.0,
        )
        availability = (
            (up_seconds / monitored_seconds) * 100.0 if monitored_seconds > 0 else None
        )
        latency_average = (
            sum(latency_values) / len(latency_values) if latency_values else None
        )
        return SyntheticSlaWindow(
            label=label,
            window_start=start,
            window_end=end,
            monitored_seconds=monitored_seconds,
            up_seconds=up_seconds,
            downtime_seconds=downtime_seconds,
            availability_percent=availability,
            outage_count=len(outages),
            longest_outage_seconds=longest_outage,
            latency_average_ms=latency_average,
            latency_p50_ms=_percentile(latency_values, 50),
            latency_p95_ms=_percentile(latency_values, 95),
        )

    @staticmethod
    def _window_outages(
        start: datetime,
        end: datetime,
        results: list[SyntheticProbeResult],
    ) -> list[SyntheticOutage]:
        outages: list[SyntheticOutage] = []
        outage_start: datetime | None = None
        last_failure_reason: str | None = None
        for result in results:
            if result.observed_at >= end:
                break
            if not result.success:
                if outage_start is None:
                    outage_start = max(start, result.observed_at)
                last_failure_reason = result.failure_reason
                continue
            if outage_start is not None:
                ended_at = min(end, result.observed_at)
                if ended_at > outage_start:
                    outages.append(
                        SyntheticOutage(
                            started_at=outage_start,
                            ended_at=ended_at,
                            active=False,
                            duration_seconds=(ended_at - outage_start).total_seconds(),
                            last_failure_reason=last_failure_reason,
                        )
                    )
                outage_start = None
                last_failure_reason = None
        if outage_start is not None and end > outage_start:
            outages.append(
                SyntheticOutage(
                    started_at=outage_start,
                    ended_at=None,
                    active=True,
                    duration_seconds=(end - outage_start).total_seconds(),
                    last_failure_reason=last_failure_reason,
                )
            )
        return outages

    @staticmethod
    def _coverage(monitor: SyntheticMonitor) -> timedelta:
        return timedelta(seconds=max(monitor.interval_seconds * 2, monitor.timeout_seconds + 5))

    @staticmethod
    def _validate_observation(observation: SyntheticProbeObservation) -> None:
        if observation.observed_at.tzinfo is None:
            raise SyntheticMonitorValidationError("synthetic observation requires timezone")
        if observation.latency_ms is not None and observation.latency_ms < 0:
            raise SyntheticMonitorValidationError("synthetic latency cannot be negative")
        if observation.http_status is not None and not 100 <= observation.http_status <= 599:
            raise SyntheticMonitorValidationError("HTTP status must be between 100 and 599")
        if observation.failure_reason is not None and len(observation.failure_reason) > 2048:
            raise SyntheticMonitorValidationError("failure reason is too long")

    @staticmethod
    def _validate_definition(
        *,
        name: str,
        monitor_type: SyntheticMonitorType,
        target: str,
        port: int | None,
        expected_status_min: int | None,
        expected_status_max: int | None,
        interval_seconds: int,
        timeout_seconds: int,
    ) -> tuple[str, str, int | None, int | None, int | None]:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 128:
            raise SyntheticMonitorValidationError("synthetic monitor name is invalid")
        if not 15 <= interval_seconds <= 3600:
            raise SyntheticMonitorValidationError("interval must be between 15 and 3600 seconds")
        if not 1 <= timeout_seconds <= 30 or timeout_seconds >= interval_seconds:
            raise SyntheticMonitorValidationError(
                "timeout must be between 1 and 30 seconds and shorter than interval"
            )

        if monitor_type is SyntheticMonitorType.HTTP:
            try:
                parsed = urlsplit(target.strip())
                parsed_port = parsed.port
            except ValueError as exc:
                raise SyntheticMonitorValidationError("HTTP target URL is invalid") from exc
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                raise SyntheticMonitorValidationError("HTTP target must use http or https")
            if parsed.username is not None or parsed.password is not None:
                raise SyntheticMonitorValidationError("HTTP target cannot contain credentials")
            _validate_host(parsed.hostname)
            if parsed_port is not None and not 1 <= parsed_port <= 65535:
                raise SyntheticMonitorValidationError("HTTP target port is invalid")
            minimum = 200 if expected_status_min is None else expected_status_min
            maximum = 399 if expected_status_max is None else expected_status_max
            if not 100 <= minimum <= maximum <= 599:
                raise SyntheticMonitorValidationError("expected HTTP status range is invalid")
            normalized = urlunsplit(
                (
                    parsed.scheme.lower(),
                    parsed.netloc,
                    parsed.path or "/",
                    parsed.query,
                    "",
                )
            )
            return clean_name, normalized, None, minimum, maximum

        normalized_host = _validate_host(target)
        if monitor_type is SyntheticMonitorType.TCP:
            if port is None or not 1 <= port <= 65535:
                raise SyntheticMonitorValidationError("TCP monitor requires a valid port")
            return clean_name, normalized_host, port, None, None
        if port is not None:
            raise SyntheticMonitorValidationError("ICMP monitor does not accept a port")
        return clean_name, normalized_host, None, None, None

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
    def _to_monitor(row: SyntheticMonitorRow) -> SyntheticMonitor:
        return SyntheticMonitor(
            id=row.id,
            device_id=row.device_id,
            name=row.name,
            monitor_type=SyntheticMonitorType(row.monitor_type),
            target=row.target,
            port=row.port,
            expected_status_min=row.expected_status_min,
            expected_status_max=row.expected_status_max,
            interval_seconds=row.interval_seconds,
            timeout_seconds=row.timeout_seconds,
            enabled=row.enabled,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_result(row: SyntheticProbeResultRow) -> SyntheticProbeResult:
        return SyntheticProbeResult(
            id=row.id,
            monitor_id=row.monitor_id,
            probe_id=row.probe_id,
            observed_at=row.observed_at,
            success=row.success,
            latency_ms=row.latency_ms,
            http_status=row.http_status,
            failure_reason=row.failure_reason,
            attributes=row.attributes,
        )
