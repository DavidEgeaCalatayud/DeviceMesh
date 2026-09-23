from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import digest_secret, generate_secret, secret_digest_matches
from app.infrastructure.database import (
    AgentCredentialRow,
    AgentRequestNonceRow,
    EnrollmentTokenRow,
    SecurityAuditEventRow,
)


class EnrollmentTokenInvalidError(Exception):
    pass


class EnrollmentTokenUsedError(Exception):
    pass


class AgentAuthenticationError(Exception):
    pass


class AgentReplayError(Exception):
    pass


class AgentCredentialNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AgentPrincipal:
    agent_id: str
    credential_id: str


@dataclass(frozen=True, slots=True)
class IssuedEnrollmentToken:
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedAgentCredential:
    agent_id: str
    credential_id: str
    credential: str


class AgentAuthService:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings

    def create_enrollment_token(
        self,
        ttl_seconds: int | None = None,
        *,
        now: datetime | None = None,
    ) -> IssuedEnrollmentToken:
        issued_at = now or datetime.now(UTC)
        ttl = ttl_seconds or self._settings.agent_enrollment_ttl_seconds
        raw_token = generate_secret()
        row = EnrollmentTokenRow(
            id=str(uuid4()),
            token_digest=digest_secret(raw_token),
            created_at=issued_at,
            expires_at=issued_at + timedelta(seconds=ttl),
            created_by="operator",
        )
        with self._session_factory() as session:
            session.add(row)
            self._audit(session, "AGENT_ENROLLMENT_TOKEN_CREATED", issued_at)
            session.commit()
        return IssuedEnrollmentToken(raw_token, row.expires_at)

    def enroll(
        self,
        token: str,
        agent_id: str,
        *,
        now: datetime | None = None,
    ) -> IssuedAgentCredential:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            token_row = session.scalar(
                select(EnrollmentTokenRow).where(
                    EnrollmentTokenRow.token_digest == digest_secret(token)
                )
            )
            if token_row is None or token_row.expires_at < current:
                self._audit(session, "AGENT_ENROLLMENT_REJECTED", current, agent_id)
                session.commit()
                raise EnrollmentTokenInvalidError
            if token_row.used_at is not None:
                self._audit(session, "AGENT_ENROLLMENT_REPLAY_REJECTED", current, agent_id)
                session.commit()
                raise EnrollmentTokenUsedError

            token_row.used_at = current
            issued = self._issue_credential(session, agent_id, current)
            self._audit(
                session,
                "AGENT_ENROLLED",
                current,
                agent_id,
                {"credentialId": issued.credential_id},
            )
            session.commit()
            return issued

    def rotate(self, agent_id: str, *, now: datetime | None = None) -> IssuedAgentCredential:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            active = session.scalars(
                select(AgentCredentialRow).where(
                    AgentCredentialRow.agent_id == agent_id,
                    AgentCredentialRow.revoked_at.is_(None),
                )
            ).all()
            previous_id = active[0].id if active else None
            for row in active:
                row.revoked_at = current
            issued = self._issue_credential(session, agent_id, current, previous_id)
            self._audit(
                session,
                "AGENT_CREDENTIAL_ROTATED",
                current,
                agent_id,
                {"credentialId": issued.credential_id},
            )
            session.commit()
            return issued

    def revoke(
        self,
        agent_id: str,
        credential_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self._session_factory() as session:
            row = session.get(AgentCredentialRow, credential_id)
            if row is None or row.agent_id != agent_id:
                raise AgentCredentialNotFoundError
            if row.revoked_at is None:
                row.revoked_at = current
            self._audit(
                session,
                "AGENT_CREDENTIAL_REVOKED",
                current,
                agent_id,
                {"credentialId": credential_id},
            )
            session.commit()

    def authenticate(
        self,
        agent_id: str,
        credential: str,
        request_timestamp: datetime,
        nonce: str,
        *,
        now: datetime | None = None,
    ) -> AgentPrincipal:
        current = now or datetime.now(UTC)
        timestamp = request_timestamp.astimezone(UTC)
        max_skew = timedelta(seconds=self._settings.agent_request_max_skew_seconds)
        if abs(current - timestamp) > max_skew:
            raise AgentAuthenticationError
        if not nonce or len(nonce) > 128:
            raise AgentAuthenticationError

        with self._session_factory() as session:
            credentials = session.scalars(
                select(AgentCredentialRow).where(
                    AgentCredentialRow.agent_id == agent_id,
                    AgentCredentialRow.revoked_at.is_(None),
                )
            ).all()
            credential_row = next(
                (
                    row
                    for row in credentials
                    if secret_digest_matches(credential, row.credential_digest)
                ),
                None,
            )
            if credential_row is None:
                raise AgentAuthenticationError

            cutoff = current - timedelta(seconds=self._settings.agent_nonce_retention_seconds)
            session.execute(delete(AgentRequestNonceRow).where(AgentRequestNonceRow.seen_at < cutoff))
            session.add(
                AgentRequestNonceRow(
                    credential_id=credential_row.id,
                    nonce=nonce,
                    seen_at=current,
                )
            )
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise AgentReplayError from exc
            return AgentPrincipal(agent_id=agent_id, credential_id=credential_row.id)

    @staticmethod
    def _issue_credential(
        session: Session,
        agent_id: str,
        created_at: datetime,
        rotated_from_id: str | None = None,
    ) -> IssuedAgentCredential:
        raw = generate_secret()
        credential_id = str(uuid4())
        session.add(
            AgentCredentialRow(
                id=credential_id,
                agent_id=agent_id,
                credential_digest=digest_secret(raw),
                created_at=created_at,
                rotated_from_id=rotated_from_id,
            )
        )
        return IssuedAgentCredential(agent_id, credential_id, raw)

    @staticmethod
    def _audit(
        session: Session,
        event_type: str,
        occurred_at: datetime,
        agent_id: str | None = None,
        attributes: dict[str, object] | None = None,
    ) -> None:
        session.add(
            SecurityAuditEventRow(
                event_type=event_type,
                agent_id=agent_id,
                occurred_at=occurred_at,
                attributes=attributes or {},
            )
        )
