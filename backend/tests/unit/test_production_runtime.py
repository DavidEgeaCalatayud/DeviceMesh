import json
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.main import app


def test_production_rejects_insecure_defaults() -> None:
    with pytest.raises(ValueError, match="unique operator token"):
        Settings(env="production")
    secure_push_key = "b" * 64
    with pytest.raises(ValueError, match="public_reads"):
        Settings(
            env="production",
            operator_token="a" * 64,
            mobile_push_encryption_secret=secure_push_key,
        )
    Settings(
        env="production",
        operator_token="a" * 64,
        mobile_push_encryption_secret=secure_push_key,
        public_reads=False,
    )


def test_readiness_reports_database_failure_without_leaking_credentials() -> None:
    with patch("app.api.routers.health.engine.connect", side_effect=OperationalError(
        "postgres://secret", {}, Exception("password"))):
        response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert response.headers["x-request-id"]


def test_json_log_excludes_exception_message() -> None:
    record = logging.LogRecord("api", logging.ERROR, "", 0, "request failed", (),
                               (ValueError, ValueError("secret"), None))
    data = json.loads(JsonFormatter().format(record))
    assert data["exception_type"] == "ValueError"
    assert "secret" not in json.dumps(data)
