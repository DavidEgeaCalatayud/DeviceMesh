import os
import re
from pathlib import Path

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def validate_secret_ref(secret_ref: str) -> None:
    if not _SECRET_REF_RE.fullmatch(secret_ref):
        raise ValueError("synthetic secret reference is invalid")


class SyntheticSecretResolver:
    def __init__(self, directory: str) -> None:
        self._directory = Path(directory)

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
        raise RuntimeError("required synthetic secret is not configured")
