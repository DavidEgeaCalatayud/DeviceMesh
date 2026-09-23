from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.application.ports import EventRepository
from app.domain.devices.models import DeviceStatus
from app.domain.events.models import DeviceEvent, EventSeverity
from app.domain.health.models import AvailabilityState
from app.infrastructure.database import DeviceRow
from app.infrastructure.repositories.health import SqlAlchemyHealthRepository


class OfflineDeviceSweeper:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        events: EventRepository,
        health: SqlAlchemyHealthRepository,
        offline_after_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._events = events
        self._health = health
        self._offline_after = timedelta(seconds=offline_after_seconds)

    def sweep(self, now: datetime | None = None) -> list[str]:
        current = now or datetime.now(UTC)
        cutoff = current - self._offline_after
        transitions: list[tuple[str, datetime | None]] = []

        with self._session_factory() as session:
            rows = session.scalars(
                select(DeviceRow).where(
                    DeviceRow.status == DeviceStatus.ONLINE.value,
                    DeviceRow.last_seen.is_not(None),
                    DeviceRow.last_seen < cutoff,
                )
            ).all()
            for row in rows:
                transitions.append((row.id, row.last_seen))
                row.status = DeviceStatus.OFFLINE.value
            session.commit()

        for device_id, last_seen in transitions:
            outage_started = (
                last_seen + self._offline_after if last_seen is not None else current
            )
            self._health.record_state(
                device_id,
                AvailabilityState.OFFLINE,
                outage_started,
                "heartbeat-timeout",
            )
            self._events.append(
                DeviceEvent(
                    device_id=device_id,
                    name="DEVICE_OFFLINE",
                    timestamp=current,
                    severity=EventSeverity.WARNING,
                    attributes={
                        "lastSeen": last_seen.isoformat() if last_seen is not None else None,
                        "outageStartedAt": outage_started.isoformat(),
                        "offlineAfterSeconds": int(self._offline_after.total_seconds()),
                    },
                )
            )
        return [device_id for device_id, _ in transitions]
