"""Human sessions never share agent/probe credentials. Only token digests persist."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.core.config import Settings
from app.infrastructure.database import Base


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(24))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HumanSessionRow(Base):
    __tablename__ = "human_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginThrottleRow(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditRow(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource: Mapped[str] = mapped_column(String(256))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


def audit(session: Session, actor: str, action: str, resource: str,
          details: dict[str, object] | None = None, source_ip: str | None = None,
          request_id: str | None = None) -> None:
    session.add(AuditRow(id=str(uuid4()), actor=actor, action=action, resource=resource,
                         timestamp=datetime.now(UTC), details=details or {},
                         source_ip=source_ip, request_id=request_id))


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass(frozen=True)
class HumanPrincipal:
    id: str
    username: str
    role: str
    session_id: str | None = None


class AuthenticationError(ValueError):
    pass


class LoginThrottled(AuthenticationError):
    pass


class HumanAuthService:
    def __init__(self, sessions: sessionmaker[Session], settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings
        self.hasher = PasswordHasher()
        self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))

    def authenticate(self, token: str) -> HumanPrincipal:
        if secrets.compare_digest(token, self.settings.operator_token):
            return HumanPrincipal("bootstrap", "bootstrap", "administrator")
        with self.sessions() as session:
            row = session.scalar(select(HumanSessionRow).where(
                HumanSessionRow.token_digest == digest(token),
                HumanSessionRow.revoked_at.is_(None),
                HumanSessionRow.expires_at > datetime.now(UTC),
            ))
            user = session.get(UserRow, row.user_id) if row else None
            if not row or not user or not user.enabled:
                raise AuthenticationError("invalid or expired session")
            return HumanPrincipal(user.id, user.username, user.role, row.id)

    def create_user(self, username: str, password: str, role: str, actor: str) -> UserRow:
        if role not in {"viewer", "operator", "administrator"}:
            raise ValueError("invalid role")
        with self.sessions.begin() as session:
            row = UserRow(id=str(uuid4()), username=username.strip().lower(),
                          password_hash=self.hasher.hash(password), role=role, enabled=True,
                          created_at=datetime.now(UTC))
            session.add(row)
            audit(session, actor, "user.created", row.id, {"role": role})
        return row

    def _throttle(self, username: str, source_ip: str) -> None:
        now = datetime.now(UTC)
        with self.sessions.begin() as session:
            for key, limit in ((digest("user:" + username), 5),
                               (digest("ip:" + source_ip), 30)):
                session.execute(insert(LoginThrottleRow).values(
                    key=key, attempts=0, started_at=now
                ).on_conflict_do_nothing(index_elements=["key"]))
                row = session.scalar(select(LoginThrottleRow).where(
                    LoginThrottleRow.key == key).with_for_update())
                assert row is not None
                if aware(row.started_at) < now - timedelta(minutes=5):
                    row.attempts, row.started_at = 0, now
                if row.attempts >= limit:
                    raise LoginThrottled("too many login attempts; retry in five minutes")
                row.attempts += 1

    def login(self, username: str, password: str, source_ip: str,
              request_id: str | None = None) -> dict[str, object]:
        username = username.strip().lower()
        self._throttle(username, source_ip)
        with self.sessions.begin() as session:
            user = session.scalar(select(UserRow).where(UserRow.username == username))
            try:
                self.hasher.verify(user.password_hash if user else self._dummy_hash, password)
                valid = user is not None and user.enabled
            except (VerificationError, InvalidHashError):
                valid = False
            if not valid or user is None:
                # Commit the denial audit independently of the error response.
                audit(session, "anonymous", "user.login_denied", "session",
                      source_ip=source_ip, request_id=request_id)
                result = None
            else:
                if self.hasher.check_needs_rehash(user.password_hash):
                    user.password_hash = self.hasher.hash(password)
                result = self._issue(session, user)
                audit(session, user.id, "user.login", "session",
                      source_ip=source_ip, request_id=request_id)
        if result is None:
            raise AuthenticationError("invalid username or password")
        return result

    def _issue(self, session: Session, user: UserRow) -> dict[str, object]:
        token, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        row = HumanSessionRow(id=str(uuid4()), user_id=user.id, token_digest=digest(token),
                              refresh_digest=digest(refresh),
                              expires_at=now + timedelta(seconds=self.settings.session_ttl_seconds),
                              refresh_expires_at=now + timedelta(seconds=self.settings.refresh_ttl_seconds))
        session.add(row)
        return {"accessToken": token, "refreshToken": refresh, "expiresAt": row.expires_at,
                "user": {"id": user.id, "username": user.username, "role": user.role}}

    def refresh(self, token: str) -> dict[str, object]:
        with self.sessions.begin() as session:
            row = session.scalar(select(HumanSessionRow).where(
                HumanSessionRow.refresh_digest == digest(token)
            ).with_for_update())
            if not row or row.revoked_at or aware(row.refresh_expires_at) <= datetime.now(UTC):
                raise AuthenticationError("invalid refresh token")
            user = session.get(UserRow, row.user_id)
            if not user or not user.enabled:
                raise AuthenticationError("invalid refresh token")
            row.revoked_at = datetime.now(UTC)
            return self._issue(session, user)

    def logout(self, principal: HumanPrincipal) -> None:
        with self.sessions.begin() as session:
            if principal.session_id:
                session.execute(update(HumanSessionRow).where(
                    HumanSessionRow.id == principal.session_id
                ).values(revoked_at=datetime.now(UTC)))
            audit(session, principal.id, "user.logout", "session")
