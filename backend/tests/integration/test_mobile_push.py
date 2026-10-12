import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.mobile_push import (
    MobilePushSubscriptionRow,
    PushTokenCipher,
    SqlAlchemyMobilePushRepository,
)
from app.infrastructure.security.human_auth import UserRow


def _create_user(role: str = "operator") -> str:
    user_id = str(uuid4())
    with SessionFactory.begin() as session:
        session.add(
            UserRow(
                id=user_id,
                username=f"push-{uuid4().hex[:10]}",
                password_hash="not-used-by-this-test",
                role=role,
                enabled=True,
                mfa_enabled=False,
                mfa_digest=None,
                created_at=datetime.now(UTC),
            )
        )
    return user_id


def test_mobile_push_tokens_are_encrypted_deduplicated_and_role_scoped() -> None:
    repository = SqlAlchemyMobilePushRepository(
        SessionFactory,
        PushTokenCipher("test-mobile-push-encryption-secret-0123456789"),
    )
    user_id = _create_user()
    installation_id = f"android-{uuid4().hex}"
    first_token = "fcm-" + ("a" * 80)

    target = repository.register(
        user_id=user_id,
        provider="fcm",
        environment="production",
        installation_id=installation_id,
        token=first_token,
    )
    assert target.token == first_token

    with SessionFactory() as session:
        row = session.scalar(
            select(MobilePushSubscriptionRow).where(
                MobilePushSubscriptionRow.id == target.id
            )
        )
        assert row is not None
        assert first_token not in row.token_ciphertext
        assert row.token_digest == hashlib.sha256(first_token.encode()).hexdigest()

    visible = repository.list_targets(roles={"operator"})
    assert any(item.id == target.id and item.token == first_token for item in visible)
    assert not any(item.id == target.id for item in repository.list_targets(roles={"viewer"}))

    rotated_token = "fcm-" + ("b" * 80)
    rotated = repository.register(
        user_id=user_id,
        provider="fcm",
        environment="production",
        installation_id=installation_id,
        token=rotated_token,
    )
    assert rotated.id == target.id
    assert rotated.token == rotated_token

    assert repository.unregister(user_id=user_id, installation_id=installation_id) == 1
    assert not any(item.id == target.id for item in repository.list_targets())


def test_push_token_cipher_rejects_tampering() -> None:
    cipher = PushTokenCipher("test-mobile-push-encryption-secret-0123456789")
    encrypted = cipher.encrypt("apns-" + ("c" * 80))
    replacement = "A" if encrypted[-1] != "A" else "B"
    tampered = encrypted[:-1] + replacement

    try:
        cipher.decrypt(tampered)
    except Exception:
        pass
    else:
        raise AssertionError("tampered AES-GCM token must not decrypt")
