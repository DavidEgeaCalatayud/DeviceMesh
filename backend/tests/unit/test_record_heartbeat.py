from datetime import UTC, datetime

from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.domain.devices.models import DeviceStatus
from app.infrastructure.repositories.in_memory import InMemoryDeviceRepository


def test_heartbeat_marks_device_online() -> None:
    repo = InMemoryDeviceRepository()
    device = RecordHeartbeat(repo).execute("agent-1", datetime.now(UTC))
    assert device.id == "agent-1"
    assert device.status is DeviceStatus.ONLINE
