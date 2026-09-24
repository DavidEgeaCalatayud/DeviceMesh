from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator, require_probe
from app.api.schemas.synthetics import (
    SyntheticHealthResponse,
    SyntheticMonitorCreateRequest,
    SyntheticMonitorResponse,
    SyntheticMonitorUpdateRequest,
    SyntheticOutageResponse,
    SyntheticProbeBatchRequest,
    SyntheticProbeResultResponse,
    SyntheticSlaWindowResponse,
)
from app.domain.synthetics.models import (
    SyntheticHealthSummary,
    SyntheticMonitor,
    SyntheticMonitorType,
    SyntheticProbeResult,
)
from app.domain.synthetics.observations import SyntheticProbeObservation
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticMonitorNotFoundError,
    SyntheticMonitorValidationError,
)
from app.runtime import get_synthetic_repository

router = APIRouter(prefix="/api/v1", tags=["synthetics"])
SyntheticRepository = Annotated[
    SqlAlchemySyntheticRepository,
    Depends(get_synthetic_repository),
]
Operator = Annotated[None, Depends(require_operator)]
Probe = Annotated[None, Depends(require_probe)]


def _monitor_response(monitor: SyntheticMonitor) -> SyntheticMonitorResponse:
    return SyntheticMonitorResponse(
        id=monitor.id,
        deviceId=monitor.device_id,
        name=monitor.name,
        monitorType=monitor.monitor_type.value,
        target=monitor.target,
        port=monitor.port,
        expectedStatusMin=monitor.expected_status_min,
        expectedStatusMax=monitor.expected_status_max,
        intervalSeconds=monitor.interval_seconds,
        timeoutSeconds=monitor.timeout_seconds,
        enabled=monitor.enabled,
        createdBy=monitor.created_by,
        createdAt=monitor.created_at,
        updatedAt=monitor.updated_at,
    )


def _result_response(result: SyntheticProbeResult) -> SyntheticProbeResultResponse:
    return SyntheticProbeResultResponse(
        id=result.id,
        monitorId=result.monitor_id,
        probeId=result.probe_id,
        observedAt=result.observed_at,
        success=result.success,
        latencyMs=result.latency_ms,
        httpStatus=result.http_status,
        failureReason=result.failure_reason,
        attributes=result.attributes,
    )


def _health_response(
    repository: SqlAlchemySyntheticRepository,
    summary: SyntheticHealthSummary,
) -> SyntheticHealthResponse:
    outages = repository.list_outages(
        summary.monitor.id,
        start=summary.generated_at - timedelta(days=30),
        end=summary.generated_at,
        limit=100,
    )
    return SyntheticHealthResponse(
        monitor=_monitor_response(summary.monitor),
        generatedAt=summary.generated_at,
        currentState=summary.current_state.value,
        currentOutageSeconds=summary.current_outage_seconds,
        stale=summary.stale,
        lastObservedAt=summary.last_observed_at,
        latestLatencyMs=summary.latest_latency_ms,
        latestHttpStatus=summary.latest_http_status,
        latestFailureReason=summary.latest_failure_reason,
        windows=[
            SyntheticSlaWindowResponse(
                label=window.label,
                windowStart=window.window_start,
                windowEnd=window.window_end,
                monitoredSeconds=window.monitored_seconds,
                upSeconds=window.up_seconds,
                downtimeSeconds=window.downtime_seconds,
                availabilityPercent=window.availability_percent,
                outageCount=window.outage_count,
                longestOutageSeconds=window.longest_outage_seconds,
                latencyAverageMs=window.latency_average_ms,
                latencyP50Ms=window.latency_p50_ms,
                latencyP95Ms=window.latency_p95_ms,
            )
            for window in summary.windows
        ],
        outages=[
            SyntheticOutageResponse(
                startedAt=outage.started_at,
                endedAt=outage.ended_at,
                active=outage.active,
                durationSeconds=outage.duration_seconds,
                lastFailureReason=outage.last_failure_reason,
            )
            for outage in outages
        ],
    )


@router.get("/synthetic-monitors", response_model=list[SyntheticMonitorResponse])
def list_synthetic_monitors(
    repository: SyntheticRepository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    enabled_only: Annotated[bool, Query(alias="enabledOnly")] = False,
) -> list[SyntheticMonitorResponse]:
    return [
        _monitor_response(monitor)
        for monitor in repository.list_monitors(
            device_id=device_id,
            enabled_only=enabled_only,
        )
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
        return _health_response(repository, repository.summarize(monitor_id))
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc


@router.get(
    "/synthetic-monitors/{monitor_id}/results",
    response_model=list[SyntheticProbeResultResponse],
)
def synthetic_monitor_results(
    monitor_id: str,
    repository: SyntheticRepository,
    hours: Annotated[int, Query(ge=1, le=24 * 30)] = 24,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[SyntheticProbeResultResponse]:
    try:
        repository.get_monitor(monitor_id)
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    now = datetime.now(UTC)
    return [
        _result_response(result)
        for result in repository.list_results(
            monitor_id,
            start=now - timedelta(hours=hours),
            end=now,
            limit=limit,
        )
    ]


@router.get(
    "/devices/{device_id}/service-health",
    response_model=list[SyntheticHealthResponse],
)
def device_service_health(
    device_id: str,
    repository: SyntheticRepository,
) -> list[SyntheticHealthResponse]:
    return [
        _health_response(repository, repository.summarize(monitor.id))
        for monitor in repository.list_monitors(device_id=device_id, enabled_only=True)
    ]


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
    try:
        monitor = repository.create_monitor(
            device_id=request.deviceId,
            name=request.name,
            monitor_type=SyntheticMonitorType(request.monitorType),
            target=request.target,
            port=request.port,
            expected_status_min=request.expectedStatusMin,
            expected_status_max=request.expectedStatusMax,
            interval_seconds=request.intervalSeconds,
            timeout_seconds=request.timeoutSeconds,
        )
    except SyntheticMonitorValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _monitor_response(monitor)


@router.put(
    "/operator/synthetic-monitors/{monitor_id}",
    response_model=SyntheticMonitorResponse,
)
def update_synthetic_monitor(
    monitor_id: str,
    request: SyntheticMonitorUpdateRequest,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticMonitorResponse:
    try:
        current = repository.get_monitor(monitor_id)
        if current.device_id != request.deviceId:
            raise SyntheticMonitorValidationError("monitor cannot be moved to another device")
        monitor = repository.update_monitor(
            monitor_id,
            name=request.name,
            monitor_type=SyntheticMonitorType(request.monitorType),
            target=request.target,
            port=request.port,
            expected_status_min=request.expectedStatusMin,
            expected_status_max=request.expectedStatusMax,
            interval_seconds=request.intervalSeconds,
            timeout_seconds=request.timeoutSeconds,
            enabled=request.enabled,
        )
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    except SyntheticMonitorValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _monitor_response(monitor)


@router.delete(
    "/operator/synthetic-monitors/{monitor_id}",
    response_model=SyntheticMonitorResponse,
)
def disable_synthetic_monitor(
    monitor_id: str,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticMonitorResponse:
    try:
        return _monitor_response(repository.disable_monitor(monitor_id))
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc


@router.get(
    "/probe/synthetic-monitors",
    response_model=list[SyntheticMonitorResponse],
)
def probe_synthetic_monitors(
    _: Probe,
    repository: SyntheticRepository,
) -> list[SyntheticMonitorResponse]:
    return [
        _monitor_response(monitor)
        for monitor in repository.list_monitors(enabled_only=True)
    ]


@router.post("/probe/synthetic-results", status_code=status.HTTP_202_ACCEPTED)
def ingest_synthetic_results(
    request: SyntheticProbeBatchRequest,
    _: Probe,
    repository: SyntheticRepository,
) -> dict[str, object]:
    observations = [
        SyntheticProbeObservation(
            monitor_id=result.monitorId,
            observed_at=result.observedAt,
            success=result.success,
            latency_ms=result.latencyMs,
            http_status=result.httpStatus,
            failure_reason=result.failureReason,
            attributes=result.attributes,
        )
        for result in request.results
    ]
    try:
        stored = repository.record_batch(request.probeId, observations)
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"monitor not found: {exc}",
        ) from exc
    except SyntheticMonitorValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return {"status": "accepted", "stored": len(stored)}
