from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.synthetics import (
    SyntheticCheckResponse,
    SyntheticHealthResponse,
    SyntheticMonitorCreateRequest,
    SyntheticMonitorResponse,
    SyntheticMonitorStateRequest,
    SyntheticSlaWindowResponse,
)
from app.domain.synthetics.models import SyntheticMonitor, SyntheticMonitorKind
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticMonitorNotFoundError,
)
from app.infrastructure.synthetics import SyntheticTargetPolicyError, validate_monitor_definition
from app.runtime import get_synthetic_repository

router = APIRouter(prefix="/api/v1", tags=["synthetics"])
SyntheticRepository = Annotated[
    SqlAlchemySyntheticRepository,
    Depends(get_synthetic_repository),
]
Operator = Annotated[None, Depends(require_operator)]


def _monitor_response(monitor: SyntheticMonitor) -> SyntheticMonitorResponse:
    return SyntheticMonitorResponse(
        id=monitor.id,
        name=monitor.name,
        kind=monitor.kind.value,
        target=monitor.target,
        port=monitor.port,
        deviceId=monitor.device_id,
        intervalSeconds=monitor.interval_seconds,
        timeoutSeconds=monitor.timeout_seconds,
        enabled=monitor.enabled,
        httpMethod=monitor.http_method,
        expectedStatus=monitor.expected_status,
        createdBy=monitor.created_by,
        createdAt=monitor.created_at,
        updatedAt=monitor.updated_at,
        nextRunAt=monitor.next_run_at,
    )


@router.get("/synthetic-monitors", response_model=list[SyntheticMonitorResponse])
def list_synthetic_monitors(
    repository: SyntheticRepository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
) -> list[SyntheticMonitorResponse]:
    return [_monitor_response(monitor) for monitor in repository.list_monitors(device_id=device_id)]


@router.post(
    "/operator/synthetic-monitors",
    response_model=SyntheticMonitorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_synthetic_monitor(
    request: SyntheticMonitorCreateRequest,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticMonitorResponse:
    kind = SyntheticMonitorKind(request.kind)
    try:
        validate_monitor_definition(
            kind=kind,
            target=request.target,
            port=request.port,
            interval_seconds=request.intervalSeconds,
            timeout_seconds=request.timeoutSeconds,
            http_method=request.httpMethod,
            expected_status=request.expectedStatus,
        )
    except SyntheticTargetPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    monitor = repository.create_monitor(
        name=request.name,
        kind=kind,
        target=request.target,
        port=request.port,
        device_id=request.deviceId,
        interval_seconds=request.intervalSeconds,
        timeout_seconds=request.timeoutSeconds,
        http_method=request.httpMethod or ("GET" if kind is SyntheticMonitorKind.HTTP else None),
        expected_status=request.expectedStatus or (200 if kind is SyntheticMonitorKind.HTTP else None),
    )
    return _monitor_response(monitor)


@router.patch(
    "/operator/synthetic-monitors/{monitor_id}/state",
    response_model=SyntheticMonitorResponse,
)
def set_synthetic_monitor_state(
    monitor_id: str,
    request: SyntheticMonitorStateRequest,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticMonitorResponse:
    try:
        monitor = repository.set_enabled(monitor_id, request.enabled, now=datetime.now(UTC))
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    return _monitor_response(monitor)


@router.get(
    "/synthetic-monitors/{monitor_id}/results",
    response_model=list[SyntheticCheckResponse],
)
def synthetic_monitor_results(
    monitor_id: str,
    repository: SyntheticRepository,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[SyntheticCheckResponse]:
    return [
        SyntheticCheckResponse(
            id=result.id,
            monitorId=result.monitor_id,
            checkedAt=result.checked_at,
            success=result.success,
            latencyMs=result.latency_ms,
            httpStatus=result.http_status,
            errorKind=result.error_kind.value if result.error_kind else None,
            error=result.error,
            probeId=result.probe_id,
        )
        for result in repository.list_results(monitor_id, limit=limit)
    ]


@router.get(
    "/synthetic-monitors/{monitor_id}/health",
    response_model=SyntheticHealthResponse,
)
def synthetic_monitor_health(
    monitor_id: str,
    repository: SyntheticRepository,
) -> SyntheticHealthResponse:
    try:
        repository.get_monitor(monitor_id)
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    summary = repository.summarize(monitor_id, datetime.now(UTC))
    return SyntheticHealthResponse(
        monitorId=summary.monitor_id,
        generatedAt=summary.generated_at,
        consecutiveFailures=summary.consecutive_failures,
        failingSince=summary.failing_since,
        windows=[
            SyntheticSlaWindowResponse(
                label=window.label,
                windowStart=window.window_start,
                windowEnd=window.window_end,
                totalChecks=window.total_checks,
                successfulChecks=window.successful_checks,
                failedChecks=window.failed_checks,
                availabilityPercent=window.availability_percent,
                meanLatencyMs=window.mean_latency_ms,
                p95LatencyMs=window.p95_latency_ms,
            )
            for window in summary.windows
        ],
    )
