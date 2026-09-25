from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.dependencies.security import require_admin, require_operator
from app.api.schemas.synthetics import (
    ProbeServiceStateResponse,
    ServiceConsensusResponse,
    ServiceIncidentResponse,
    ServiceIncidentSummaryResponse,
    SyntheticCheckResponse,
    SyntheticHealthResponse,
    SyntheticMonitorCreateRequest,
    SyntheticMonitorResponse,
    SyntheticMonitorStateRequest,
    SyntheticProbeAssignmentResponse,
    SyntheticProbeAssignmentStateRequest,
    SyntheticProbeCreateRequest,
    SyntheticProbeHeartbeatResponse,
    SyntheticProbeRegistrationResponse,
    SyntheticProbeResponse,
    SyntheticProbeStateRequest,
    SyntheticSlaWindowResponse,
    SyntheticWorkMonitorResponse,
    SyntheticWorkResponse,
    SyntheticWorkResultRequest,
)
from app.core.config import get_settings
from app.domain.synthetics.models import (
    ServiceIncident,
    SyntheticMonitor,
    SyntheticMonitorKind,
    SyntheticProbe,
)
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticMonitorNotFoundError,
    SyntheticProbeAuthenticationError,
    SyntheticProbeNotFoundError,
    SyntheticWorkNotFoundError,
)
from app.infrastructure.synthetics import SyntheticTargetPolicyError, validate_monitor_definition
from app.runtime import get_synthetic_repository

router = APIRouter(prefix="/api/v1", tags=["synthetics"])
SyntheticRepository = Annotated[
    SqlAlchemySyntheticRepository,
    Depends(get_synthetic_repository),
]
Operator = Annotated[None, Depends(require_operator)]
Authorization = Annotated[str | None, Header(alias="Authorization")]


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
        failureThreshold=monitor.failure_threshold,
        recoveryThreshold=monitor.recovery_threshold,
        createdBy=monitor.created_by,
        createdAt=monitor.created_at,
        updatedAt=monitor.updated_at,
        nextRunAt=monitor.next_run_at,
    )


def _probe_response(probe: SyntheticProbe, now: datetime) -> SyntheticProbeResponse:
    settings = get_settings()
    online_after = now - timedelta(seconds=settings.synthetic_probe_offline_after_seconds)
    online = probe.enabled and probe.last_seen_at is not None and probe.last_seen_at >= online_after
    return SyntheticProbeResponse(
        id=probe.id,
        name=probe.name,
        location=probe.location,
        capabilities=[item.value for item in probe.capabilities],
        enabled=probe.enabled,
        lastSeenAt=probe.last_seen_at,
        online=online,
        createdAt=probe.created_at,
        updatedAt=probe.updated_at,
    )


def _incident_response(incident: ServiceIncident, now: datetime) -> ServiceIncidentResponse:
    return ServiceIncidentResponse(
        id=incident.id,
        monitorId=incident.monitor_id,
        state=incident.state.value,
        classification=incident.classification.value,
        openedAt=incident.opened_at,
        resolvedAt=incident.resolved_at,
        lastObservedAt=incident.last_observed_at,
        durationSeconds=incident.duration_seconds(now),
        failureThreshold=incident.failure_threshold,
        recoveryThreshold=incident.recovery_threshold,
        maintenanceActiveAtOpen=incident.maintenance_active_at_open,
        hostOfflineAtOpen=incident.host_offline_at_open,
        failingProbes=incident.failing_probes,
        totalProbes=incident.total_probes,
    )


def _require_probe(repository: SqlAlchemySyntheticRepository, authorization: str | None) -> SyntheticProbe:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="probe token required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return repository.authenticate_probe(token)
    except SyntheticProbeAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


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
        failure_threshold=request.failureThreshold,
        recovery_threshold=request.recoveryThreshold,
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
            probeLocation=result.probe_location,
            workId=result.work_id,
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


@router.get(
    "/synthetic-monitors/{monitor_id}/consensus",
    response_model=ServiceConsensusResponse,
)
def synthetic_monitor_consensus(
    monitor_id: str,
    repository: SyntheticRepository,
) -> ServiceConsensusResponse:
    try:
        summary = repository.consensus(monitor_id, datetime.now(UTC))
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    return ServiceConsensusResponse(
        monitorId=summary.monitor_id,
        generatedAt=summary.generated_at,
        classification=summary.classification.value,
        healthyProbes=summary.healthy_probes,
        failingProbes=summary.failing_probes,
        states=[
            ProbeServiceStateResponse(
                probeId=item.probe_id,
                location=item.location,
                success=item.success,
                checkedAt=item.checked_at,
                latencyMs=item.latency_ms,
            )
            for item in summary.states
        ],
    )


@router.get(
    "/synthetic-monitors/{monitor_id}/incidents",
    response_model=ServiceIncidentSummaryResponse,
)
def synthetic_monitor_incidents(
    monitor_id: str,
    repository: SyntheticRepository,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ServiceIncidentSummaryResponse:
    now = datetime.now(UTC)
    try:
        repository.get_monitor(monitor_id)
    except SyntheticMonitorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor not found") from exc
    summary = repository.incidents(monitor_id, limit=limit, now=now)
    return ServiceIncidentSummaryResponse(
        monitorId=summary.monitor_id,
        openIncident=(
            _incident_response(summary.open_incident, now) if summary.open_incident else None
        ),
        incidents=[_incident_response(item, now) for item in summary.incidents],
        resolvedCount=summary.resolved_count,
        meanRecoverySeconds=summary.mean_recovery_seconds,
    )


@router.post(
    "/operator/synthetic-probes",
    response_model=SyntheticProbeRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_synthetic_probe(
    request: SyntheticProbeCreateRequest,
    _: Annotated[None, Depends(require_admin)],
    repository: SyntheticRepository,
) -> SyntheticProbeRegistrationResponse:
    now = datetime.now(UTC)
    registration = repository.create_probe(
        name=request.name,
        location=request.location,
        capabilities=tuple(SyntheticMonitorKind(value) for value in request.capabilities),
        now=now,
    )
    return SyntheticProbeRegistrationResponse(
        probe=_probe_response(registration.probe, now),
        token=registration.token,
    )


@router.get(
    "/operator/synthetic-probes",
    response_model=list[SyntheticProbeResponse],
)
def list_synthetic_probes(
    _: Operator,
    repository: SyntheticRepository,
) -> list[SyntheticProbeResponse]:
    now = datetime.now(UTC)
    return [_probe_response(probe, now) for probe in repository.list_probes()]


@router.patch(
    "/operator/synthetic-probes/{probe_id}/state",
    response_model=SyntheticProbeResponse,
)
def set_synthetic_probe_state(
    probe_id: str,
    request: SyntheticProbeStateRequest,
    _: Annotated[None, Depends(require_admin)],
    repository: SyntheticRepository,
) -> SyntheticProbeResponse:
    now = datetime.now(UTC)
    try:
        probe = repository.set_probe_enabled(probe_id, request.enabled, now=now)
    except SyntheticProbeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="probe not found") from exc
    return _probe_response(probe, now)


@router.get(
    "/operator/synthetic-probe-assignments",
    response_model=list[SyntheticProbeAssignmentResponse],
)
def list_synthetic_probe_assignments(
    _: Operator,
    repository: SyntheticRepository,
    monitor_id: Annotated[str | None, Query(alias="monitorId")] = None,
) -> list[SyntheticProbeAssignmentResponse]:
    return [
        SyntheticProbeAssignmentResponse(
            monitorId=item.monitor_id,
            probeId=item.probe_id,
            enabled=item.enabled,
            nextRunAt=item.next_run_at,
            createdAt=item.created_at,
            updatedAt=item.updated_at,
        )
        for item in repository.list_assignments(monitor_id)
    ]


@router.put(
    "/operator/synthetic-monitors/{monitor_id}/probes/{probe_id}",
    response_model=SyntheticProbeAssignmentResponse,
)
def assign_synthetic_probe(
    monitor_id: str,
    probe_id: str,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticProbeAssignmentResponse:
    try:
        item = repository.assign_probe(monitor_id, probe_id, now=datetime.now(UTC))
    except (SyntheticMonitorNotFoundError, SyntheticProbeNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor or probe not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SyntheticProbeAssignmentResponse(
        monitorId=item.monitor_id,
        probeId=item.probe_id,
        enabled=item.enabled,
        nextRunAt=item.next_run_at,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


@router.patch(
    "/operator/synthetic-monitors/{monitor_id}/probes/{probe_id}",
    response_model=SyntheticProbeAssignmentResponse,
)
def set_synthetic_probe_assignment_state(
    monitor_id: str,
    probe_id: str,
    request: SyntheticProbeAssignmentStateRequest,
    _: Operator,
    repository: SyntheticRepository,
) -> SyntheticProbeAssignmentResponse:
    try:
        item = repository.set_assignment_enabled(
            monitor_id,
            probe_id,
            request.enabled,
            now=datetime.now(UTC),
        )
    except SyntheticProbeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found") from exc
    return SyntheticProbeAssignmentResponse(
        monitorId=item.monitor_id,
        probeId=item.probe_id,
        enabled=item.enabled,
        nextRunAt=item.next_run_at,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


@router.post("/probes/heartbeat", response_model=SyntheticProbeHeartbeatResponse)
def synthetic_probe_heartbeat(
    repository: SyntheticRepository,
    authorization: Authorization = None,
) -> SyntheticProbeHeartbeatResponse:
    probe = _require_probe(repository, authorization)
    updated = repository.heartbeat_probe(probe.id, now=datetime.now(UTC))
    assert updated.last_seen_at is not None
    return SyntheticProbeHeartbeatResponse(probeId=updated.id, lastSeenAt=updated.last_seen_at)


@router.get("/probes/work", response_model=list[SyntheticWorkResponse])
def claim_synthetic_probe_work(
    repository: SyntheticRepository,
    authorization: Authorization = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SyntheticWorkResponse]:
    probe = _require_probe(repository, authorization)
    settings = get_settings()
    items = repository.claim_probe_work(
        probe.id,
        now=datetime.now(UTC),
        limit=limit,
        lease_seconds=settings.synthetic_probe_work_lease_seconds,
    )
    return [
        SyntheticWorkResponse(
            workId=item.id,
            assignedAt=item.assigned_at,
            leaseExpiresAt=item.lease_expires_at,
            monitor=SyntheticWorkMonitorResponse(
                id=item.monitor.id,
                name=item.monitor.name,
                kind=item.monitor.kind.value,
                target=item.monitor.target,
                port=item.monitor.port,
                timeoutSeconds=item.monitor.timeout_seconds,
                httpMethod=item.monitor.http_method,
                expectedStatus=item.monitor.expected_status,
            ),
        )
        for item in items
    ]


@router.post("/probes/results", response_model=SyntheticCheckResponse)
def submit_synthetic_probe_result(
    request: SyntheticWorkResultRequest,
    repository: SyntheticRepository,
    authorization: Authorization = None,
) -> SyntheticCheckResponse:
    probe = _require_probe(repository, authorization)
    from app.domain.synthetics.models import SyntheticCheckErrorKind

    try:
        result = repository.complete_probe_work(
            work_id=request.workId,
            probe_id=probe.id,
            success=request.success,
            latency_ms=request.latencyMs,
            http_status=request.httpStatus,
            error_kind=(SyntheticCheckErrorKind(request.errorKind) if request.errorKind else None),
            error=request.error,
            checked_at=request.checkedAt,
        )
    except SyntheticWorkNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="work item not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SyntheticCheckResponse(
        id=result.id,
        monitorId=result.monitor_id,
        checkedAt=result.checked_at,
        success=result.success,
        latencyMs=result.latency_ms,
        httpStatus=result.http_status,
        errorKind=result.error_kind.value if result.error_kind else None,
        error=result.error,
        probeId=result.probe_id,
        probeLocation=result.probe_location,
        workId=result.work_id,
    )
