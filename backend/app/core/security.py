import hashlib
import hmac
import secrets


def generate_secret() -> str:
    """Return a high-entropy opaque secret suitable for one-time or agent credentials."""
    return secrets.token_urlsafe(32)


def generate_enrollment_token() -> str:
    return generate_secret()


def digest_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def secret_digest_matches(secret: str, expected_digest: str) -> bool:
    return hmac.compare_digest(digest_secret(secret), expected_digest)
