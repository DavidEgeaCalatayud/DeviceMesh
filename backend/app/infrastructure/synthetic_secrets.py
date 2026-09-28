import os
import re
from pathlib import Path

from app.core.config import Settings

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}$")
_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}


def validate_secret_ref(secret_ref: str) -> None:
    if not _SECRET_REF_RE.fullmatch(secret_ref):
        raise ValueError("synthetic secret reference is invalid")


def validate_header_name(name: str) -> None:
    if not _HEADER_NAME_RE.fullmatch(name):
        raise ValueError("synthetic HTTP header name is invalid")


def header_requires_secret(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in _SENSITIVE_HEADER_NAMES
        or "token" in lowered
        or "secret" in lowered
        or "api-key" in lowered
        or "apikey" in lowered
    )


class SyntheticSecretResolver:
    def __init__(self, settings: Settings) -> None:
        self._directory = Path(settings.synthetic_secret_directory)

    def resolve(self, secret_ref: str) -> str:
        validate_secret_ref(secret_ref)
        path = self._directory / secret_ref
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        key = "DEVICEMESH_SYNTHETIC_SECRET_" + re.sub(
            r"[^A-Za-z0-9]",
            "_",
            secret_ref,
        ).upper()
        value = os.environ.get(key, "").strip()
        if value:
            return value
        raise RuntimeError(f"synthetic secret '{secret_ref}' is not configured")
