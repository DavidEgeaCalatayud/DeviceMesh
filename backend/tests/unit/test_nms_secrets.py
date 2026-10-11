from pathlib import Path

import pytest

from app.core.config import Settings
from app.infrastructure.nms_secrets import NmsSecretResolver, validate_nms_secret_ref


def test_nms_secret_reference_validation_is_bounded() -> None:
    validate_nms_secret_ref("switch-core.auth")
    with pytest.raises(ValueError):
        validate_nms_secret_ref("../secret")
    with pytest.raises(ValueError):
        validate_nms_secret_ref("x" * 129)


def test_nms_secret_resolver_reads_file_and_redacts_missing_reference(tmp_path: Path) -> None:
    secret = tmp_path / "switch-core.auth"
    secret.write_text("super-secret-passphrase\n", encoding="utf-8")
    resolver = NmsSecretResolver(Settings(nms_secret_directory=str(tmp_path)))
    assert resolver.resolve("switch-core.auth") == "super-secret-passphrase"

    with pytest.raises(RuntimeError) as exc_info:
        resolver.resolve("missing-auth")
    message = str(exc_info.value)
    assert "missing-auth" not in message
    assert "super-secret-passphrase" not in message
