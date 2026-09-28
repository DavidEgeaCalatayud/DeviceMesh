from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies.security import require_operator
from app.infrastructure.database import SessionFactory
from app.infrastructure.probe_runtime import ProbeRuntimeService
from app.infrastructure.repositories.synthetics import (
    SqlAlchemySyntheticRepository,
    SyntheticProbeAuthenticationError,
)
from app.runtime import get_synthetic_repository

router = APIRouter(prefix="/api/v1", tags=["synthetics"])
SyntheticRepository = Annotated[
    SqlAlchemySyntheticRepository,
    Depends(get_synthetic_repository),
]
Authorization = Annotated[str | None, Header(alias="Authorization")]
Operator = Annotated[None, Depends(require_operator)]


class ProbeRuntimeHeartbeatRequest(BaseModel):
    agentVersion: str = Field(min_length=1, max_length=32)
    uptimeSeconds: int = Field(ge=0, le=2_147_483_647)
    queueDepth: int = Field(ge=0, le=1_000_000)
    queueCapacity: int = Field(gt=0, le=1_000_000)
    maxConcurrentChecks: int = Field(gt=0, le=1024)


class ProbeRuntimeResponse(BaseModel):
    probeId: str
    credentialRotatedAt: datetime
    credentialExpiresAt: datetime
    agentVersion: str | None
    uptimeSeconds: int | None
    queueDepth: int | None
    queueCapacity: int | None
    maxConcurrentChecks: int | None
    reportedAt: datetime | None


def _probe_id(repository: SqlAlchemySyntheticRepository, authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="probe token required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return repository.authenticate_probe(token).id
    except SyntheticProbeAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def _response(probe_id: str) -> ProbeRuntimeResponse:
    try:
        snapshot = ProbeRuntimeService(SessionFactory).get(probe_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="probe not found") from exc
    return ProbeRuntimeResponse(
        probeId=snapshot.probe_id,
        credentialRotatedAt=snapshot.credential_rotated_at,
        credentialExpiresAt=snapshot.credential_expires_at,
        agentVersion=snapshot.agent_version,
        uptimeSeconds=snapshot.uptime_seconds,
        queueDepth=snapshot.queue_depth,
        queueCapacity=snapshot.queue_capacity,
        maxConcurrentChecks=snapshot.max_concurrent_checks,
        reportedAt=snapshot.reported_at,
    )


@router.post("/probes/runtime-heartbeat", response_model=ProbeRuntimeResponse)
def probe_runtime_heartbeat(
    request: ProbeRuntimeHeartbeatRequest,
    repository: SyntheticRepository,
    authorization: Authorization = None,
) -> ProbeRuntimeResponse:
    if request.queueDepth > request.queueCapacity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="queueDepth cannot exceed queueCapacity",
        )
    probe_id = _probe_id(repository, authorization)
    now = datetime.now(UTC)
    repository.heartbeat_probe(probe_id, now=now)
    snapshot = ProbeRuntimeService(SessionFactory).record(
        probe_id,
        agent_version=request.agentVersion,
        uptime_seconds=request.uptimeSeconds,
        queue_depth=request.queueDepth,
        queue_capacity=request.queueCapacity,
        max_concurrent_checks=request.maxConcurrentChecks,
        now=now,
    )
    return ProbeRuntimeResponse(
        probeId=snapshot.probe_id,
        credentialRotatedAt=snapshot.credential_rotated_at,
        credentialExpiresAt=snapshot.credential_expires_at,
        agentVersion=snapshot.agent_version,
        uptimeSeconds=snapshot.uptime_seconds,
        queueDepth=snapshot.queue_depth,
        queueCapacity=snapshot.queue_capacity,
        maxConcurrentChecks=snapshot.max_concurrent_checks,
        reportedAt=snapshot.reported_at,
    )


@router.get(
    "/operator/synthetic-probes/{probe_id}/runtime",
    response_model=ProbeRuntimeResponse,
)
def probe_runtime_status(probe_id: str, _: Operator) -> ProbeRuntimeResponse:
    return _response(probe_id)
