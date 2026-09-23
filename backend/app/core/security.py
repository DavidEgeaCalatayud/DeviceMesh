import secrets


def generate_enrollment_token() -> str:
    """Generate a high-entropy one-time enrollment token."""
    return secrets.token_urlsafe(32)
