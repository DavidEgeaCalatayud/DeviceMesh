from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.infrastructure.database import Base
from app.infrastructure.security.human_auth import UserRow

PushProvider = Literal["fcm", "apns"]
PushEnvironment = Literal["production", "sandbox"]
_AAD = b"DeviceMesh mobile push token v1"


@dataclass(frozen=True, slots=True)
class PushTarget:
    id: str
    user_id: str
    provider: PushProvider
    environment: PushEnvironment
    installation_id: str
    token: str


class MobilePushSubscriptionRow(Base):
    __tablename__ = "mobile_push_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            "installation_id",
            name="uq_mobile_push_user_provider_installation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    installation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_ciphertext: Mapped[str] = mapped_column(String(8192), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PushTokenCipher:
    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("mobile push encryption secret must contain at least 32 characters")
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()

    def encrypt(self, token: str) -> str:
        if not 16 <= len(token) <= 4096:
            raise ValueError("push token length is invalid")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, token.encode("utf-8"), _AAD)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, value: str) -> str:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        if len(raw) < 29:
            raise ValueError("push token ciphertext is invalid")
        plaintext = AESGCM(self._key).decrypt(raw[:12], raw[12:], _AAD)
        return plaintext.decode("utf-8")


class SqlAlchemyMobilePushRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        cipher: PushTokenCipher,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def register(
        self,
        *,
        user_id: str,
        provider: PushProvider,
        environment: PushEnvironment,
        installation_id: str,
        token: str,
    ) -> PushTarget:
        now = datetime.now(UTC)
        token_digest = self._digest(token)
        token_ciphertext = self._cipher.encrypt(token)
        with self._session_factory.begin() as session:
            if session.get(UserRow, user_id) is None:
                raise LookupError("user not found")
            by_token = session.scalar(
                select(MobilePushSubscriptionRow)
                .where(MobilePushSubscriptionRow.token_digest == token_digest)
                .with_for_update()
            )
            by_installation = session.scalar(
                select(MobilePushSubscriptionRow)
                .where(
                    MobilePushSubscriptionRow.user_id == user_id,
                    MobilePushSubscriptionRow.provider == provider,
                    MobilePushSubscriptionRow.installation_id == installation_id,
                )
                .with_for_update()
            )
            if by_token is not None:
                row = by_token
                if by_installation is not None and by_installation.id != row.id:
                    session.delete(by_installation)
                    session.flush()
            elif by_installation is not None:
                row = by_installation
            else:
                row = MobilePushSubscriptionRow(
                    id=str(uuid4()),
                    user_id=user_id,
                    provider=provider,
                    environment=environment,
                    installation_id=installation_id,
                    token_digest=token_digest,
                    token_ciphertext=token_ciphertext,
                    created_at=now,
                    updated_at=now,
                    enabled=True,
                )
                session.add(row)
            row.user_id = user_id
            row.provider = provider
            row.environment = environment
            row.installation_id = installation_id
            row.token_digest = token_digest
            row.token_ciphertext = token_ciphertext
            row.updated_at = now
            row.enabled = True
            session.flush()
            return self._target(row)

    def unregister(self, *, user_id: str, installation_id: str) -> int:
        with self._session_factory.begin() as session:
            rows = list(
                session.scalars(
                    select(MobilePushSubscriptionRow)
                    .where(
                        MobilePushSubscriptionRow.user_id == user_id,
                        MobilePushSubscriptionRow.installation_id == installation_id,
                    )
                    .with_for_update()
                )
            )
            for row in rows:
                session.delete(row)
            return len(rows)

    def list_targets(
        self,
        *,
        user_ids: set[str] | None = None,
        roles: set[str] | None = None,
    ) -> list[PushTarget]:
        statement = (
            select(MobilePushSubscriptionRow)
            .join(UserRow, UserRow.id == MobilePushSubscriptionRow.user_id)
            .where(
                MobilePushSubscriptionRow.enabled.is_(True),
                UserRow.enabled.is_(True),
            )
            .order_by(MobilePushSubscriptionRow.id)
        )
        if user_ids:
            statement = statement.where(MobilePushSubscriptionRow.user_id.in_(sorted(user_ids)))
        if roles:
            statement = statement.where(UserRow.role.in_(sorted(roles)))
        with self._session_factory() as session:
            rows = list(session.scalars(statement))
        return [self._target(row) for row in rows]

    def disable(self, target_id: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(MobilePushSubscriptionRow, target_id)
            if row is not None:
                row.enabled = False
                row.updated_at = datetime.now(UTC)

    def _target(self, row: MobilePushSubscriptionRow) -> PushTarget:
        provider: PushProvider
        environment: PushEnvironment
        if row.provider not in {"fcm", "apns"}:
            raise ValueError("stored push provider is invalid")
        if row.environment not in {"production", "sandbox"}:
            raise ValueError("stored push environment is invalid")
        provider = row.provider
        environment = row.environment
        return PushTarget(
            id=row.id,
            user_id=row.user_id,
            provider=provider,
            environment=environment,
            installation_id=row.installation_id,
            token=self._cipher.decrypt(row.token_ciphertext),
        )
