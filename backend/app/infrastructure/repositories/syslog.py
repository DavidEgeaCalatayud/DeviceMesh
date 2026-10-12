from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, delete, func, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.syslog import SyslogMessage
from app.infrastructure.database import Base, DeviceInterfaceRow, DeviceRow


class SyslogMessageRow(Base):
    __tablename__ = "syslog_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), index=True)
    facility: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    severity: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), index=True)
    app_name: Mapped[str | None] = mapped_column(String(128))
    proc_id: Mapped[str | None] = mapped_column(String(64))
    msg_id: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(4096), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)


class SqlAlchemySyslogRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def append(
        self,
        *,
        received_at: datetime,
        source_address: str,
        facility: int,
        severity: int,
        hostname: str | None,
        app_name: str | None,
        proc_id: str | None,
        msg_id: str | None,
        message: str,
        protocol: str,
    ) -> SyslogMessage:
        with self._session_factory.begin() as session:
            device_id = self._resolve_device(session, source_address, hostname)
            row = SyslogMessageRow(
                received_at=received_at,
                source_address=source_address,
                device_id=device_id,
                facility=facility,
                severity=severity,
                hostname=hostname,
                app_name=app_name,
                proc_id=proc_id,
                msg_id=msg_id,
                message=message[:4096],
                protocol=protocol,
            )
            session.add(row)
            session.flush()
            return self._to_domain(row)

    def search(
        self,
        *,
        device_id: str | None = None,
        source_address: str | None = None,
        severity: int | None = None,
        facility: int | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        query_text: str | None = None,
        limit: int = 200,
    ) -> list[SyslogMessage]:
        statement = select(SyslogMessageRow)
        if device_id is not None:
            statement = statement.where(SyslogMessageRow.device_id == device_id)
        if source_address is not None:
            statement = statement.where(SyslogMessageRow.source_address == source_address)
        if severity is not None:
            statement = statement.where(SyslogMessageRow.severity == severity)
        if facility is not None:
            statement = statement.where(SyslogMessageRow.facility == facility)
        if start is not None:
            statement = statement.where(SyslogMessageRow.received_at >= start)
        if end is not None:
            statement = statement.where(SyslogMessageRow.received_at <= end)
        if query_text:
            escaped = query_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            needle = f"%{escaped}%"
            statement = statement.where(
                or_(
                    SyslogMessageRow.message.ilike(needle, escape="\\"),
                    SyslogMessageRow.hostname.ilike(needle, escape="\\"),
                    SyslogMessageRow.app_name.ilike(needle, escape="\\"),
                )
            )
        bounded = min(max(limit, 1), 1000)
        statement = statement.order_by(
            SyslogMessageRow.received_at.desc(),
            SyslogMessageRow.id.desc(),
        ).limit(bounded)
        with self._session_factory() as session:
            return [self._to_domain(row) for row in session.scalars(statement).all()]

    def delete_before(self, cutoff: datetime) -> int:
        with self._session_factory.begin() as session:
            count = session.scalar(
                select(func.count(SyslogMessageRow.id)).where(
                    SyslogMessageRow.received_at < cutoff
                )
            ) or 0
            session.execute(
                delete(SyslogMessageRow).where(SyslogMessageRow.received_at < cutoff)
            )
            return int(count)

    @staticmethod
    def _resolve_device(
        session: Session,
        source_address: str,
        hostname: str | None,
    ) -> str | None:
        interface = session.scalar(
            select(DeviceInterfaceRow)
            .where(DeviceInterfaceRow.ip_address == source_address)
            .limit(1)
        )
        if interface is not None:
            return interface.device_id
        if hostname:
            device = session.scalar(
                select(DeviceRow)
                .where(func.lower(DeviceRow.hostname) == hostname.casefold())
                .limit(1)
            )
            if device is not None:
                return device.id
        return None

    @staticmethod
    def _to_domain(row: SyslogMessageRow) -> SyslogMessage:
        return SyslogMessage(
            id=row.id,
            received_at=row.received_at,
            source_address=row.source_address,
            device_id=row.device_id,
            facility=row.facility,
            severity=row.severity,
            hostname=row.hostname,
            app_name=row.app_name,
            proc_id=row.proc_id,
            msg_id=row.msg_id,
            message=row.message,
            protocol=row.protocol,
        )
