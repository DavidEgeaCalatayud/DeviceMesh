import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("deployment_config", Path(__file__).parents[1] / "config.py")
assert spec and spec.loader
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def test_no_env_execution_and_no_silent_rotation(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.write_text("DEVICEMESH_DOMAIN=$(touch /tmp/must-not-execute)\n")
    with pytest.raises(ValueError, match="interpolation"):
        config.read_env(env)
    directory = tmp_path / "secrets"
    config.initialize(directory)
    first = (directory / "operator_token").read_bytes()
    config.initialize(directory)
    assert first == (directory / "operator_token").read_bytes()
    assert directory.stat().st_mode & 0o777 == 0o700


def test_partial_secrets_and_bad_origins_fail_closed(tmp_path: Path) -> None:
    directory = tmp_path / "secrets"
    directory.mkdir()
    (directory / "operator_token").write_text("test")
    with pytest.raises(ValueError, match="partial"):
        config.initialize(directory)
    with pytest.raises(ValueError, match="CORS"):
        config.validate({"DEVICEMESH_DOMAIN": "mesh.internal", "DEVICEMESH_CORS_ORIGINS": '["*"]'}, False)
