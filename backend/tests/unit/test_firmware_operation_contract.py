import pytest
from pydantic import ValidationError

from app.api.schemas.operations import RemoteOperationCreateRequest
from app.domain.operations.models import RemoteOperationType


def test_firmware_update_is_allowlisted_and_strictly_bounded() -> None:
    request = RemoteOperationCreateRequest(
        deviceId="device-1",
        operationType="firmware.update",
        arguments={
            "url": "https://updates.example.com/devicemesh-esp32.bin",
            "sha256": "a" * 64,
            "version": "1.2.3",
        },
    )
    assert request.operationType == RemoteOperationType.FIRMWARE_UPDATE.value

    with pytest.raises(ValidationError):
        RemoteOperationCreateRequest(
            deviceId="device-1",
            operationType="firmware.update",
            arguments={
                "url": "http://updates.example.com/devicemesh-esp32.bin",
                "sha256": "a" * 64,
                "version": "1.2.3",
            },
        )

    with pytest.raises(ValidationError):
        RemoteOperationCreateRequest(
            deviceId="device-1",
            operationType="firmware.update",
            arguments={
                "url": "https://updates.example.com/devicemesh-esp32.bin",
                "sha256": "not-a-digest",
                "version": "1.2.3",
            },
        )

    with pytest.raises(ValidationError):
        RemoteOperationCreateRequest(
            deviceId="device-1",
            operationType="firmware.update",
            arguments={
                "url": "https://updates.example.com/devicemesh-esp32.bin",
                "sha256": "a" * 64,
                "version": "1.2.3",
                "command": "rm -rf /",
            },
        )
