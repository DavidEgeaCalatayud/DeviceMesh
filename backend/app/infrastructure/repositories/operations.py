from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.operations.models import (
    RemoteOperation,
    RemoteOperationStatus,
    RemoteOperationType,
)
from app.infrastructure.database import AgentRow, RemoteOperationRow, SecurityAuditEventRow


class NoAgentForDeviceError(Exception):
    pass


class RemoteOperationNotFoundError(Exception):
    pass


class InvalidRemoteOperationTransitionError(Exception):
    pass


class SqlAlchemyRemoteOperationRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def queue(
        self,
        *,
        device_id: str,
        operation_type: RemoteOperationType,
        arguments: dict[str, object] | None = None,
        ttl_seconds: int = 300,
        requested_by: str = "operator",
        now: datetime | None = None,
    ) -> RemoteOperation:
        self._validate_arguments(operation_type, arguments or {})
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            agent = session.scalar(
                select(AgentRow)
                .where(AgentRow.device_id == device_id)
                .order_by(AgentRow.last_seen.desc().nullslast(), AgentRow.id)
                .limit(1)
            )
            if agent is None:
                raise NoAgentForDeviceError
            row = RemoteOperationRow(
                id=str(uuid4()),
                device_id=device_id,
                agent_id=agent.id,
                operation_type=operation_type.value,
                arguments=arguments or {},
                status=RemoteOperationStatus.QUEUED.value,
                requested_by=requested_by,
                created_at=current,
                expires_at=current + timedelta(seconds=ttl_seconds),
                result={},
            )
            session.add(row)
            self._audit(
                session,
                "REMOTE_OPERATION_QUEUED",
                current,
                agent.id,
                {
                    "operationId": row.id,
                    "deviceId": device_id,
                    "operationType": operation_type.value,
                    "expiresAt": row.expires_at.isoformat(),
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def list_operations(
        self,
        *,
        device_id: str | None = None,
        limit: int = 100,
        now: datetime | None = None,
    ) -> list[RemoteOperation]:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            self._expire_pending(session, current)
            statement = select(RemoteOperationRow)
            if device_id is not None:
                statement = statement.where(RemoteOperationRow.device_id == device_id)
            rows = session.scalars(
                statement.order_by(RemoteOperationRow.created_at.desc()).limit(
                    min(max(limit, 1), 500)
                )
            ).all()
            session.commit()
            return [self._to_domain(row) for row in rows]

    def claim_next(
        self,
        agent_id: str,
        *,
        now: datetime | None = None,
    ) -> RemoteOperation | None:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            self._expire_pending(session, current, agent_id=agent_id)
            row = session.scalar(
                select(RemoteOperationRow)
                .where(
                    RemoteOperationRow.agent_id == agent_id,
                    RemoteOperationRow.status == RemoteOperationStatus.QUEUED.value,
                    RemoteOperationRow.expires_at > current,
                )
                .order_by(RemoteOperationRow.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                session.commit()
                return None
            row.status = RemoteOperationStatus.CLAIMED.value
            row.claimed_at = current
            self._audit(
                session,
                "REMOTE_OPERATION_CLAIMED",
                current,
                agent_id,
                {
                    "operationId": row.id,
                    "deviceId": row.device_id,
                    "operationType": row.operation_type,
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def complete(
        self,
        *,
        agent_id: str,
        operation_id: str,
        succeeded: bool,
        result: dict[str, object] | None = None,
        error: str | None = None,
        now: datetime | None = None,
    ) -> RemoteOperation:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.scalar(
                select(RemoteOperationRow)
                .where(RemoteOperationRow.id == operation_id)
                .with_for_update()
                .limit(1)
            )
            if row is None or row.agent_id != agent_id:
                raise RemoteOperationNotFoundError
            if (
                row.status == RemoteOperationStatus.CLAIMED.value
                and row.expires_at <= current
            ):
                self._expire_row(session, row, current)
                session.commit()
                raise InvalidRemoteOperationTransitionError
            if row.status != RemoteOperationStatus.CLAIMED.value:
                raise InvalidRemoteOperationTransitionError
            row.status = (
                RemoteOperationStatus.SUCCEEDED.value
                if succeeded
                else RemoteOperationStatus.FAILED.value
            )
            row.completed_at = current
            row.result = result or {}
            row.error = error[:1024] if error else None
            self._audit(
                session,
                "REMOTE_OPERATION_COMPLETED",
                current,
                agent_id,
                {
                    "operationId": row.id,
                    "deviceId": row.device_id,
                    "operationType": row.operation_type,
                    "status": row.status,
                },
            )
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    def _expire_pending(
        self,
        session: Session,
        now: datetime,
        *,
        agent_id: str | None = None,
    ) -> None:
        statement = select(RemoteOperationRow).where(
            RemoteOperationRow.status.in_(
                (
                    RemoteOperationStatus.QUEUED.value,
                    RemoteOperationStatus.CLAIMED.value,
                )
            ),
            RemoteOperationRow.expires_at <= now,
        )
        if agent_id is not None:
            statement = statement.where(RemoteOperationRow.agent_id == agent_id)
        rows = session.scalars(statement.with_for_update(skip_locked=True)).all()
        for row in rows:
            self._expire_row(session, row, now)

    def _expire_row(
        self,
        session: Session,
        row: RemoteOperationRow,
        now: datetime,
    ) -> None:
        previous_status = row.status
        row.status = RemoteOperationStatus.EXPIRED.value
        row.completed_at = now
        row.error = f"operation expired while {previous_status}"
        self._audit(
            session,
            "REMOTE_OPERATION_EXPIRED",
            now,
            row.agent_id,
            {
                "operationId": row.id,
                "deviceId": row.device_id,
                "operationType": row.operation_type,
                "previousStatus": previous_status,
            },
        )

    @staticmethod
    def _validate_arguments(
        operation_type: RemoteOperationType,
        arguments: dict[str, object],
    ) -> None:
        if operation_type is RemoteOperationType.NETWORK_DNS_LOOKUP:
            if set(arguments) != {"hostname"}:
                raise ValueError("network.dns_lookup requires only hostname")
            hostname = arguments.get("hostname")
            if not isinstance(hostname, str) or not 1 <= len(hostname.strip()) <= 253:
                raise ValueError("hostname must be 1-253 characters")
            return
        if operation_type is RemoteOperationType.FIRMWARE_UPDATE:
            if set(arguments) != {"url", "sha256", "version"}:
                raise ValueError("firmware.update requires url, sha256 and version")
            url = arguments.get("url")
            sha256 = arguments.get("sha256")
            version = arguments.get("version")
            if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2048:
                raise ValueError("firmware update URL must use HTTPS")
            if (
                not isinstance(sha256, str)
                or len(sha256) != 64
                or any(character not in "0123456789abcdefABCDEF" for character in sha256)
            ):
                raise ValueError("firmware update sha256 must be hexadecimal")
            if not isinstance(version, str) or not 1 <= len(version.strip()) <= 64:
                raise ValueError("firmware update version must be 1-64 characters")
            return
        if arguments:
            raise ValueError(f"{operation_type.value} does not accept arguments in V1.1")

    @staticmethod
    def _audit(
        session: Session,
        event_type: str,
        occurred_at: datetime,
        agent_id: str,
        attributes: dict[str, object],
    ) -> None:
        session.add(
            SecurityAuditEventRow(
                event_type=event_type,
                agent_id=agent_id,
                occurred_at=occurred_at,
                attributes=attributes,
            )
        )

    @staticmethod
    def _to_domain(row: RemoteOperationRow) -> RemoteOperation:
        return RemoteOperation(
            id=row.id,
            device_id=row.device_id,
            agent_id=row.agent_id,
            operation_type=RemoteOperationType(row.operation_type),
            status=RemoteOperationStatus(row.status),
            requested_by=row.requested_by,
            created_at=row.created_at,
            expires_at=row.expires_at,
            arguments=row.arguments,
            claimed_at=row.claimed_at,
            completed_at=row.completed_at,
            result=row.result,
            error=row.error,
        )
