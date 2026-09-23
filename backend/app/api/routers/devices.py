from fastapi import APIRouter

from app.runtime import device_repository

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("")
def list_devices() -> list[dict[str, object]]:
    return [
        {
            "id": device.id,
            "hostname": device.hostname,
            "ipAddresses": sorted(device.ip_addresses),
            "macAddresses": sorted(device.mac_addresses),
            "operatingSystem": device.operating_system,
            "operatingSystemVersion": device.operating_system_version,
            "architecture": device.architecture,
            "manufacturer": device.manufacturer,
            "status": device.status.value,
            "firstSeen": device.first_seen,
            "lastSeen": device.last_seen,
        }
        for device in device_repository.list_devices()
    ]
