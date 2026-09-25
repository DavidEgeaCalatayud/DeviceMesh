import json
from datetime import UTC, datetime, timedelta

from devicemesh_probe.health import ProbeHealthState


def test_probe_health_state_is_atomic_and_recent(tmp_path) -> None:
    path = tmp_path / "probe-health.json"
    state = ProbeHealthState(path)

    state.write()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "alive"
    assert isinstance(payload["pid"], int)
    assert state.healthy(45) is True
    assert not path.with_suffix(".json.tmp").exists()


def test_probe_health_state_rejects_stale_or_invalid_files(tmp_path) -> None:
    path = tmp_path / "probe-health.json"
    state = ProbeHealthState(path)

    assert state.healthy(45) is False

    path.write_text("not-json", encoding="utf-8")
    assert state.healthy(45) is False

    old = datetime.now(UTC) - timedelta(minutes=5)
    path.write_text(json.dumps({"status": "alive", "updatedAt": old.isoformat()}), encoding="utf-8")
    assert state.healthy(45) is False
