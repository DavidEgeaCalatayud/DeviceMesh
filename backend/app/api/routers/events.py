from fastapi import APIRouter, Query

from app.runtime import event_repository

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
def list_events(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
    return [
        {
            "deviceId": event.device_id,
            "name": event.name,
            "timestamp": event.timestamp,
            "severity": event.severity.value,
            "attributes": event.attributes,
        }
        for event in event_repository.list_recent(limit)
    ]
