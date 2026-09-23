from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.events.models import DeviceEvent, EventSeverity
from app.infrastructure.database import DeviceEventRow


class SqlAlchemyEventRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def append(self, event: DeviceEvent) -> None:
        with self._session_factory() as session:
            session.add(
                DeviceEventRow(
                    device_id=event.device_id,
                    name=event.name,
                    severity=event.severity.value,
                    timestamp=event.timestamp,
                    attributes=event.attributes,
                )
            )
            session.commit()

    def list_recent(self, limit: int = 100) -> list[DeviceEvent]:
        bounded_limit = min(max(limit, 1), 500)
        with self._session_factory() as session:
            rows = session.scalars(
                select(DeviceEventRow)
                .order_by(desc(DeviceEventRow.timestamp), desc(DeviceEventRow.id))
                .limit(bounded_limit)
            ).all()
            return [
                DeviceEvent(
                    device_id=row.device_id,
                    name=row.name,
                    timestamp=row.timestamp,
                    severity=EventSeverity(row.severity),
                    attributes=row.attributes,
                )
                for row in rows
            ]
