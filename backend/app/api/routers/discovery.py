from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.schemas.discovery import DiscoveryBatchRequest
from app.application.use_cases.record_observation import RecordObservation
from app.domain.devices.models import DeviceObservation
from app.runtime import get_observation_use_case

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])

ObservationUseCase = Annotated[RecordObservation, Depends(get_observation_use_case)]


@router.post("/observations", status_code=status.HTTP_202_ACCEPTED)
def observations(
    request: DiscoveryBatchRequest,
    use_case: ObservationUseCase,
) -> dict[str, object]:
    device_ids: list[str] = []
    for payload in request.observations:
        device = use_case.execute(
            DeviceObservation(
                source=payload.source,
                observed_at=payload.observedAt,
                hostname=payload.hostname,
                ip_address=payload.ipAddress,
                mac_address=payload.macAddress,
                manufacturer=payload.manufacturer,
                attributes=payload.attributes,
            )
        )
        device_ids.append(device.id)
    return {"status": "accepted", "deviceIds": sorted(set(device_ids))}
