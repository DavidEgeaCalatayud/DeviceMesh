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


def validate_http_settings(
    headers: dict[str, str],
    secret_headers: dict[str, str],
    expected_body_contains: str | None,
    *,
    http_method: str | None,
) -> None:
    if len(headers) > 32 or len(secret_headers) > 32:
        raise ValueError("synthetic HTTP monitors allow at most 32 headers of each type")
    lowered_plain: set[str] = set()
    for name, value in headers.items():
        validate_header_name(name)
        if header_requires_secret(name):
            raise ValueError(f"sensitive HTTP header '{name}' must use a secret reference")
        if not isinstance(value, str) or len(value) > 1024 or "\r" in value or "\n" in value:
            raise ValueError(f"HTTP header '{name}' has an invalid value")
        lowered_plain.add(name.lower())
    lowered_secret: set[str] = set()
    for name, secret_ref in secret_headers.items():
        validate_header_name(name)
        validate_secret_ref(secret_ref)
        if name.lower() in lowered_plain:
            raise ValueError(f"HTTP header '{name}' is configured as both plain and secret")
        lowered_secret.add(name.lower())
    if len(lowered_secret) != len(secret_headers):
        raise ValueError("synthetic secret header names must be unique case-insensitively")
    if expected_body_contains is not None:
        if not expected_body_contains or len(expected_body_contains) > 512:
            raise ValueError("expectedBodyContains must contain between 1 and 512 characters")
        if (http_method or "GET").upper() == "HEAD":
            raise ValueError("expectedBodyContains cannot be used with HEAD monitors")


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
