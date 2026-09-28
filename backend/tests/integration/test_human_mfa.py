import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.infrastructure.database import Base
from app.infrastructure.security.human_auth import (
    AuthenticationError,
    HumanAuthService,
    HumanSessionRow,
    UserRow,
)


def auth_service() -> tuple[HumanAuthService, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    return HumanAuthService(sessions, Settings(operator_token="a" * 48)), sessions


def test_mfa_factor_is_hashed_required_rotatable_and_recoverable() -> None:
    auth, sessions = auth_service()
    user = auth.create_user("operator", "correct horse battery", "operator", "test")

    initial = auth.login("operator", "correct horse battery", "127.0.0.1")
    assert initial["user"]["mfaEnabled"] is False

    factor = auth.enable_or_rotate_mfa(user.id, user.id)
    assert len(factor) >= 40
    with sessions() as session:
        stored = session.get(UserRow, user.id)
        assert stored is not None
        assert stored.mfa_enabled is True
        assert stored.mfa_digest is not None
        assert stored.mfa_digest != factor
        assert len(stored.mfa_digest) == 64
        previous_session = session.scalar(select(HumanSessionRow))
        assert previous_session is not None and previous_session.revoked_at is not None

    with pytest.raises(AuthenticationError):
        auth.login("operator", "correct horse battery", "127.0.0.2")
    with pytest.raises(AuthenticationError):
        auth.login("operator", "correct horse battery", "127.0.0.3", mfa_code="wrong-factor-code-xxxxxxxx")

    secured = auth.login("operator", "correct horse battery", "127.0.0.4", mfa_code=factor)
    assert secured["user"]["mfaEnabled"] is True

    rotated = auth.enable_or_rotate_mfa(user.id, user.id)
    assert rotated != factor
    with pytest.raises(AuthenticationError):
        auth.login("operator", "correct horse battery", "127.0.0.5", mfa_code=factor)
    auth.login("operator", "correct horse battery", "127.0.0.6", mfa_code=rotated)

    auth.disable_mfa(user.id, "", "administrator", administrator_override=True)
    password_only = auth.login("operator", "correct horse battery", "127.0.0.7")
    assert password_only["user"]["mfaEnabled"] is False


def test_mfa_cannot_be_disabled_with_wrong_factor() -> None:
    auth, _ = auth_service()
    user = auth.create_user("viewer", "correct horse battery", "viewer", "test")
    factor = auth.enable_or_rotate_mfa(user.id, user.id)

    with pytest.raises(AuthenticationError):
        auth.disable_mfa(user.id, "wrong-factor-code-xxxxxxxx", user.id)

    auth.disable_mfa(user.id, factor, user.id)
    auth.login("viewer", "correct horse battery", "127.0.0.8")
