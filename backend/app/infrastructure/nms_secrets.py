import os
import re
from pathlib import Path

from app.core.config import Settings

_SECRET_REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def validate_nms_secret_ref(secret_ref: str) -> None:
    if not _SECRET_REF_RE.fullmatch(secret_ref):
        raise ValueError("NMS secret reference is invalid")


class NmsSecretResolver:
    def __init__(self, settings: Settings) -> None:
        self._directory = Path(settings.nms_secret_directory)

    def resolve(self, secret_ref: str) -> str:
        validate_nms_secret_ref(secret_ref)
        path = self._directory / secret_ref
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
        key = "DEVICEMESH_NMS_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", secret_ref).upper()
        value = os.environ.get(key, "").strip()
        if value:
            return value
        raise RuntimeError("NMS credential is not configured")
