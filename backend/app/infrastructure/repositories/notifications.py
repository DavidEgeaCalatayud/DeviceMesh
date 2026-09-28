from datetime import datetime, timedelta

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, or_, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.domain.alerts.models import AlertTransition
from app.domain.alerts.notifications import (
    NotificationChannel,
    NotificationChannelKind,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationRoute,
    NotificationTransitionFilter,
)
from app.infrastructure.database import Base


class NotificationChannelRow(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationRouteRow(Base):
    __tablename__ = "notification_routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("notification_channels.id"), nullable=False)
    transition: Mapped[str] = mapped_column(String(16), nullable=False)
    metric_name: Mapped[str | None] = mapped_column(String(128))
    device_id: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationDeliveryRow(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_delivery_dedupe"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("notification_channels.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("notification_routes.id"), nullable=False)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), nullable=False)
    transition: Mapped[str] = mapped_column(String(16), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlAlchemyNotificationRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_channel(
        self,
        *,
        name: str,
        kind: NotificationChannelKind,
        secret_ref: str,
        config: dict[str, object],
    ) -> NotificationChannel:
        with self._session_factory.begin() as session:
            if session.scalar(select(NotificationChannelRow.id).where(NotificationChannelRow.name == name)):
                raise ValueError("notification channel name already exists")
            row = NotificationChannelRow(
                name=name,
                kind=kind.value,
                secret_ref=secret_ref,
                config=config,
                enabled=True,
            )
            session.add(row)
            session.flush()
            return self._channel(row)

    def list_channels(self) -> list[NotificationChannel]:
        with self._session_factory() as session:
            rows = session.scalars(select(NotificationChannelRow).order_by(NotificationChannelRow.id)).all()
            return [self._channel(row) for row in rows]

    def set_channel_enabled(self, channel_id: int, enabled: bool) -> NotificationChannel:
        with self._session_factory.begin() as session:
            row = session.get(NotificationChannelRow, channel_id)
            if row is None:
                raise LookupError("notification channel not found")
            row.enabled = enabled
            session.flush()
            return self._channel(row)

    def create_route(
        self,
        *,
        name: str,
        channel_id: int,
        transition: NotificationTransitionFilter,
        metric_name: str | None,
        device_id: str | None,
    ) -> NotificationRoute:
        with self._session_factory.begin() as session:
            if session.get(NotificationChannelRow, channel_id) is None:
                raise LookupError("notification channel not found")
            if session.scalar(select(NotificationRouteRow.id).where(NotificationRouteRow.name == name)):
                raise ValueError("notification route name already exists")
            row = NotificationRouteRow(
                name=name,
                channel_id=channel_id,
                transition=transition.value,
                metric_name=metric_name,
                device_id=device_id,
                enabled=True,
            )
            session.add(row)
            session.flush()
            return self._route(row)

    def list_routes(self) -> list[NotificationRoute]:
        with self._session_factory() as session:
            rows = session.scalars(select(NotificationRouteRow).order_by(NotificationRouteRow.id)).all()
            return [self._route(row) for row in rows]

    def set_route_enabled(self, route_id: int, enabled: bool) -> NotificationRoute:
        with self._session_factory.begin() as session:
            row = session.get(NotificationRouteRow, route_id)
            if row is None:
                raise LookupError("notification route not found")
            row.enabled = enabled
            session.flush()
            return self._route(row)

    def enqueue_transition(self, transition: AlertTransition) -> int:
        # Maintenance windows silence both opening and recovery notifications.
        if transition.incident.maintenance_window_id is not None:
            return 0
        transition_name = transition.type.value
        condition = transition.rule.condition
        payload: dict[str, object] = {
            "event": f"alert.{transition_name}",
            "alertId": transition.incident.id,
            "ruleId": transition.rule.id,
            "deviceId": transition.incident.device_id,
            "metricName": condition.metric_name,
            "operator": condition.operator,
            "threshold": condition.threshold,
            "durationSeconds": condition.duration_seconds,
            "value": transition.value,
            "timestamp": transition.timestamp.isoformat(),
        }
        created = 0
        with self._session_factory.begin() as session:
            rows = session.execute(
                select(NotificationRouteRow, NotificationChannelRow)
                .join(NotificationChannelRow, NotificationChannelRow.id == NotificationRouteRow.channel_id)
                .where(NotificationRouteRow.enabled.is_(True), NotificationChannelRow.enabled.is_(True))
                .order_by(NotificationRouteRow.id)
            ).all()
            for route, channel in rows:
                if route.transition not in {transition_name, NotificationTransitionFilter.BOTH.value}:
                    continue
                if route.metric_name is not None and route.metric_name != condition.metric_name:
                    continue
                if route.device_id is not None and route.device_id != transition.incident.device_id:
                    continue
                dedupe = f"alert:{transition.incident.id}:{transition_name}:route:{route.id}:channel:{channel.id}"
                exists = session.scalar(
                    select(NotificationDeliveryRow.id).where(NotificationDeliveryRow.dedupe_key == dedupe)
                )
                if exists is not None:
                    continue
                session.add(
                    NotificationDeliveryRow(
                        channel_id=channel.id,
                        route_id=route.id,
                        alert_id=transition.incident.id,
                        transition=transition_name,
                        dedupe_key=dedupe,
                        payload=payload,
                        status=NotificationDeliveryStatus.QUEUED.value,
                        attempts=0,
                        next_attempt_at=transition.timestamp,
                        created_at=transition.timestamp,
                    )
                )
                created += 1
        return created

    def list_deliveries(
        self,
        *,
        status: NotificationDeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[NotificationDelivery]:
        statement = select(NotificationDeliveryRow).order_by(NotificationDeliveryRow.id.desc())
        if status is not None:
            statement = statement.where(NotificationDeliveryRow.status == status.value)
        with self._session_factory() as session:
            rows = session.scalars(statement.limit(limit)).all()
            return [self._delivery(row) for row in rows]

    def claim_due(
        self,
        now: datetime,
        *,
        limit: int,
        lease_seconds: int,
    ) -> list[tuple[NotificationDelivery, NotificationChannel]]:
        lease_until = now + timedelta(seconds=lease_seconds)
        with self._session_factory.begin() as session:
            rows = session.scalars(
                select(NotificationDeliveryRow)
                .where(
                    NotificationDeliveryRow.status == NotificationDeliveryStatus.QUEUED.value,
                    NotificationDeliveryRow.next_attempt_at <= now,
                    or_(
                        NotificationDeliveryRow.locked_until.is_(None),
                        NotificationDeliveryRow.locked_until < now,
                    ),
                )
                .order_by(NotificationDeliveryRow.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            claimed: list[tuple[NotificationDelivery, NotificationChannel]] = []
            for row in rows:
                channel = session.get(NotificationChannelRow, row.channel_id)
                if channel is None or not channel.enabled:
                    continue
                row.attempts += 1
                row.last_attempt_at = now
                row.locked_until = lease_until
                session.flush()
                claimed.append((self._delivery(row), self._channel(channel)))
            return claimed

    def mark_delivered(self, delivery_id: int, now: datetime) -> None:
        with self._session_factory.begin() as session:
            row = session.get(NotificationDeliveryRow, delivery_id)
            if row is None:
                raise LookupError("notification delivery not found")
            row.status = NotificationDeliveryStatus.DELIVERED.value
            row.delivered_at = now
            row.locked_until = None
            row.last_error = None

    def mark_failed(
        self,
        delivery_id: int,
        now: datetime,
        error: str,
        *,
        max_attempts: int,
    ) -> None:
        with self._session_factory.begin() as session:
            row = session.get(NotificationDeliveryRow, delivery_id)
            if row is None:
                raise LookupError("notification delivery not found")
            row.locked_until = None
            row.last_error = error[:512]
            if row.attempts >= max_attempts:
                row.status = NotificationDeliveryStatus.DEAD.value
                return
            delay_seconds = min(3600, 5 * (2 ** max(0, row.attempts - 1)))
            row.status = NotificationDeliveryStatus.QUEUED.value
            row.next_attempt_at = now + timedelta(seconds=delay_seconds)

    def retry_delivery(self, delivery_id: int, now: datetime) -> NotificationDelivery:
        with self._session_factory.begin() as session:
            row = session.get(NotificationDeliveryRow, delivery_id)
            if row is None:
                raise LookupError("notification delivery not found")
            if row.status == NotificationDeliveryStatus.DELIVERED.value:
                raise ValueError("delivered notification cannot be retried")
            row.status = NotificationDeliveryStatus.QUEUED.value
            row.attempts = 0
            row.next_attempt_at = now
            row.locked_until = None
            row.last_error = None
            session.flush()
            return self._delivery(row)

    @staticmethod
    def _channel(row: NotificationChannelRow) -> NotificationChannel:
        return NotificationChannel(
            id=row.id,
            name=row.name,
            kind=NotificationChannelKind(row.kind),
            secret_ref=row.secret_ref,
            config=dict(row.config),
            enabled=row.enabled,
        )

    @staticmethod
    def _route(row: NotificationRouteRow) -> NotificationRoute:
        return NotificationRoute(
            id=row.id,
            name=row.name,
            channel_id=row.channel_id,
            transition=NotificationTransitionFilter(row.transition),
            metric_name=row.metric_name,
            device_id=row.device_id,
            enabled=row.enabled,
        )

    @staticmethod
    def _delivery(row: NotificationDeliveryRow) -> NotificationDelivery:
        return NotificationDelivery(
            id=row.id,
            channel_id=row.channel_id,
            route_id=row.route_id,
            alert_id=row.alert_id,
            transition=row.transition,
            payload=dict(row.payload),
            status=NotificationDeliveryStatus(row.status),
            attempts=row.attempts,
            next_attempt_at=row.next_attempt_at,
            last_attempt_at=row.last_attempt_at,
            delivered_at=row.delivered_at,
            last_error=row.last_error,
        )
