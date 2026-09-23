from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.health import (
    DeviceHealthResponse,
    MaintenanceWindowCreateRequest,
    MaintenanceWindowResponse,
    OutageResponse,
    SlaWindowResponse,
)
from app.domain.events.models import DeviceEvent
from app.domain.health.models import MaintenanceWindow
from app.infrastructure.repositories.health import (
    MaintenanceWindowNotFoundError,
    SqlAlchemyHealthRepository,
    SqlAlchemyMaintenanceRepository,
)
from app.runtime import (
    event_repository,
    get_health_repository,
    get_maintenance_repository,
)

router = APIRouter(prefix="/api/v1", tags=["operational-health"])
HealthRepository = Annotated[SqlAlchemyHealthRepository, Depends(get_health_repository)]
MaintenanceRepository = Annotated[
    SqlAlchemyMaintenanceRepository,
    Depends(get_maintenance_repository),
]
Operator = Annotated[None, Depends(require_operator)]


def _maintenance_response(
    window: MaintenanceWindow,
    now: datetime | None = None,
) -> MaintenanceWindowResponse:
    current = now or datetime.now(UTC)
    return MaintenanceWindowResponse(
        id=window.id,
        deviceId=window.device_id,
        startsAt=window.starts_at,
        endsAt=window.ends_at,
        reason=window.reason,
        createdBy=window.created_by,
        createdAt=window.created_at,
        cancelledAt=window.cancelled_at,
        active=window.is_active(current),
    )


@router.get("/devices/{device_id}/health", response_model=DeviceHealthResponse)
def device_health(
    device_id: str,
    health: HealthRepository,
    maintenance: MaintenanceRepository,
) -> DeviceHealthResponse:
    now = datetime.now(UTC)
    summary = health.summarize(device_id, now)
    active_maintenance = maintenance.active_window(device_id, now)
    return DeviceHealthResponse(
        deviceId=summary.device_id,
        generatedAt=summary.generated_at,
        currentState=summary.current_state.value if summary.current_state is not None else None,
        currentOutageSeconds=summary.current_outage_seconds,
        maintenanceActive=active_maintenance is not None,
        maintenanceWindowId=active_maintenance.id if active_maintenance is not None else None,
        windows=[
            SlaWindowResponse(
                label=window.label,
                windowStart=window.window_start,
                windowEnd=window.window_end,
                monitoredSeconds=window.monitored_seconds,
                onlineSeconds=window.online_seconds,
                downtimeSeconds=window.downtime_seconds,
                availabilityPercent=window.availability_percent,
                outageCount=window.outage_count,
                longestOutageSeconds=window.longest_outage_seconds,
                meanRecoverySeconds=window.mean_recovery_seconds,
            )
            for window in summary.windows
        ],
    )


@router.get("/devices/{device_id}/outages", response_model=list[OutageResponse])
def device_outages(
    device_id: str,
    health: HealthRepository,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[OutageResponse]:
    now = datetime.now(UTC)
    intervals = health.list_outages(
        device_id,
        now - timedelta(days=days),
        now,
        limit=limit,
    )
    return [
        OutageResponse(
            id=interval.id,
            deviceId=interval.device_id,
            startedAt=interval.started_at,
            endedAt=interval.ended_at,
            durationSeconds=interval.duration_seconds(now),
            active=interval.ended_at is None,
            source=interval.source,
        )
        for interval in intervals
    ]


@router.get("/maintenance-windows", response_model=list[MaintenanceWindowResponse])
def list_maintenance_windows(
    maintenance: MaintenanceRepository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    active_only: Annotated[bool, Query(alias="activeOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[MaintenanceWindowResponse]:
    now = datetime.now(UTC)
    return [
        _maintenance_response(window, now)
        for window in maintenance.list_windows(
            device_id=device_id,
            active_only=active_only,
            at=now,
            limit=limit,
        )
    ]


@router.post(
    "/operator/maintenance-windows",
    response_model=MaintenanceWindowResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance_window(
    request: MaintenanceWindowCreateRequest,
    _: Operator,
    maintenance: MaintenanceRepository,
) -> MaintenanceWindowResponse:
    if request.startsAt.tzinfo is None or request.endsAt.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="maintenance timestamps must include a timezone",
        )
    now = datetime.now(UTC)
    try:
        window = maintenance.create(
            device_id=request.deviceId,
            starts_at=request.startsAt,
            ends_at=request.endsAt,
            reason=request.reason,
            created_at=now,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if window.device_id is not None:
        event_repository.append(
            DeviceEvent(
                device_id=window.device_id,
                name="MAINTENANCE_SCHEDULED",
                timestamp=now,
                attributes={
                    "maintenanceWindowId": window.id,
                    "startsAt": window.starts_at.isoformat(),
                    "endsAt": window.ends_at.isoformat(),
                    "reason": window.reason,
                },
            )
        )
    return _maintenance_response(window, now)


@router.post(
    "/operator/maintenance-windows/{window_id}/cancel",
    response_model=MaintenanceWindowResponse,
)
def cancel_maintenance_window(
    window_id: int,
    _: Operator,
    maintenance: MaintenanceRepository,
) -> MaintenanceWindowResponse:
    now = datetime.now(UTC)
    try:
        window = maintenance.cancel(window_id, now)
    except MaintenanceWindowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="window not found") from exc
    if window.device_id is not None:
        event_repository.append(
            DeviceEvent(
                device_id=window.device_id,
                name="MAINTENANCE_CANCELLED",
                timestamp=now,
                attributes={"maintenanceWindowId": window.id},
            )
        )
    return _maintenance_response(window, now)
