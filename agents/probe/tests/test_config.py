import os
from pathlib import Path

import pytest

from devicemesh_probe.config import ProbeConfig


def _clear_probe_token_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVICEMESH_PROBE_TOKEN", raising=False)
    monkeypatch.delenv("DEVICEMESH_PROBE_TOKEN_FILE", raising=False)
    monkeypatch.delenv("DEVICEMESH_PROBE_SCOPES", raising=False)
    monkeypatch.delenv("DEVICEMESH_PROBE_TCP_PORTS", raising=False)


def test_probe_token_can_be_loaded_from_secret_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_probe_token_environment(monkeypatch)
    secret = tmp_path / "probe-token"
    secret.write_text("rotated-secret\n", encoding="utf-8")
    monkeypatch.setenv("DEVICEMESH_PROBE_TOKEN_FILE", str(secret))

    config = ProbeConfig.from_environment()

    assert config.require_synthetic_token() == "rotated-secret"


def test_probe_rejects_ambiguous_token_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_probe_token_environment(monkeypatch)
    secret = tmp_path / "probe-token"
    secret.write_text("file-secret", encoding="utf-8")
    monkeypatch.setenv("DEVICEMESH_PROBE_TOKEN", "environment-secret")
    monkeypatch.setenv("DEVICEMESH_PROBE_TOKEN_FILE", str(secret))

    with pytest.raises(ValueError, match="configure only one"):
        ProbeConfig.from_environment()
