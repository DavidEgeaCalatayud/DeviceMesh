from fastapi import APIRouter

from app.runtime import telemetry_repository

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.get("/latest")
def latest_metrics() -> list[dict[str, object]]:
    return [
        {
            "deviceId": sample.device_id,
            "timestamp": sample.timestamp,
            "name": sample.metric.name,
            "value": sample.metric.value,
            "unit": sample.metric.unit,
        }
        for sample in telemetry_repository.list_latest()
    ]
