from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.domain.devices.models import DeviceIdentity
from app.infrastructure.database import SessionFactory
from app.infrastructure.offline import OfflineDeviceSweeper
from app.main import app
from app.runtime import device_repository, event_repository


def test_offline_transition_is_deduplicated_and_recovers() -> None:
    agent_id = f"offline-{uuid4().hex[:8]}"
    old = datetime.now(UTC) - timedelta(minutes=10)
    identity = DeviceIdentity(hostname=agent_id)
    device = device_repository.mark_agent_online(agent_id, old, identity)
    sweeper = OfflineDeviceSweeper(
        SessionFactory,
        event_repository,
        offline_after_seconds=60,
    )

    first = sweeper.sweep(datetime.now(UTC))
    second = sweeper.sweep(datetime.now(UTC))
    assert device.id in first
    assert second == []

    device_repository.mark_agent_online(agent_id, datetime.now(UTC), identity)
    names = [
        event.name
        for event in event_repository.list_recent(100)
        if event.device_id == device.id
    ]
    assert names.count("DEVICE_OFFLINE") == 1
    assert "DEVICE_ONLINE" in names


def test_websocket_receives_persisted_device_event() -> None:
    mac = ":".join(["02", "42", *(uuid4().hex[index : index + 2] for index in range(0, 8, 2))])
    payload = {
        "observations": [
            {
                "source": "realtime-test",
                "observedAt": datetime.now(UTC).isoformat(),
                "hostname": f"ws-{uuid4().hex[:8]}",
                "ipAddress": "192.0.2.25",
                "macAddress": mac,
                "attributes": {"latencyMs": 2.5},
            }
        ]
    }
    with TestClient(app) as client:
        with client.websocket_connect("/ws/events") as websocket:
            response = client.post("/api/v1/discovery/observations", json=payload)
            assert response.status_code == 202
            envelope = websocket.receive_json()
            assert envelope["type"] == "device.event"
            assert envelope["payload"]["name"] == "DEVICE_DISCOVERED"
