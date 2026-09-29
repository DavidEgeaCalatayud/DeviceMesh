from dataclasses import dataclass

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.database import Base


@dataclass(frozen=True, slots=True)
class SyntheticHttpSettings:
    monitor_id: str
    headers: dict[str, str]
    secret_headers: dict[str, str]
    expected_body_contains: str | None


class SyntheticHttpSettingsRow(Base):
    __tablename__ = "synthetic_http_settings"

    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_monitors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    headers: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    secret_headers: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    expected_body_contains: Mapped[str | None] = mapped_column(String(512))


class SqlAlchemySyntheticHttpSettingsRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def set(
        self,
        monitor_id: str,
        *,
        headers: dict[str, str],
        secret_headers: dict[str, str],
        expected_body_contains: str | None,
    ) -> SyntheticHttpSettings:
        with self._session_factory.begin() as session:
            row = session.get(SyntheticHttpSettingsRow, monitor_id)
            if row is None:
                row = SyntheticHttpSettingsRow(
                    monitor_id=monitor_id,
                    headers=dict(headers),
                    secret_headers=dict(secret_headers),
                    expected_body_contains=expected_body_contains,
                )
                session.add(row)
            else:
                row.headers = dict(headers)
                row.secret_headers = dict(secret_headers)
                row.expected_body_contains = expected_body_contains
            session.flush()
            return self._model(row)

    def get(self, monitor_id: str) -> SyntheticHttpSettings:
        with self._session_factory() as session:
            row = session.get(SyntheticHttpSettingsRow, monitor_id)
            if row is None:
                return SyntheticHttpSettings(
                    monitor_id=monitor_id,
                    headers={},
                    secret_headers={},
                    expected_body_contains=None,
                )
            return self._model(row)

    @staticmethod
    def _model(row: SyntheticHttpSettingsRow) -> SyntheticHttpSettings:
        return SyntheticHttpSettings(
            monitor_id=row.monitor_id,
            headers=dict(row.headers),
            secret_headers=dict(row.secret_headers),
            expected_body_contains=row.expected_body_contains,
        )
