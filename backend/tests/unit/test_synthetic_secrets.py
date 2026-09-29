from pathlib import Path

import pytest

from app.core.config import Settings
from app.infrastructure.synthetic_secrets import SyntheticSecretResolver, validate_http_settings


def test_sensitive_headers_require_secret_references() -> None:
    with pytest.raises(ValueError, match="must use a secret reference"):
        validate_http_settings(
            {"Authorization": "Bearer plaintext"},
            {},
            None,
            http_method="GET",
        )


def test_body_assertion_rejects_head() -> None:
    with pytest.raises(ValueError, match="HEAD"):
        validate_http_settings({}, {}, "healthy", http_method="HEAD")


def test_resolver_reads_file_without_exposing_value(tmp_path: Path) -> None:
    secret = tmp_path / "payments-api"
    secret.write_text("Bearer ultra-secret\n", encoding="utf-8")
    resolver = SyntheticSecretResolver(Settings(synthetic_secret_directory=str(tmp_path)))
    assert resolver.resolve("payments-api") == "Bearer ultra-secret"


def test_missing_secret_error_is_handled_by_executor_without_value(tmp_path: Path) -> None:
    resolver = SyntheticSecretResolver(Settings(synthetic_secret_directory=str(tmp_path)))
    with pytest.raises(RuntimeError) as exc_info:
        resolver.resolve("missing-api-token")
    assert "missing-api-token" in str(exc_info.value)
    assert "Bearer" not in str(exc_info.value)
