from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies.security import require_agent_principal, require_operator
from app.api.schemas.operations import (
    RemoteOperationClaimResponse,
    RemoteOperationCompleteRequest,
    RemoteOperationCreateRequest,
    RemoteOperationResponse,
)
from app.domain.operations.models import RemoteOperation, RemoteOperationType
from app.infrastructure.repositories.operations import (
    InvalidRemoteOperationTransitionError,
    NoAgentForDeviceError,
    RemoteOperationNotFoundError,
    SqlAlchemyRemoteOperationRepository,
)
from app.infrastructure.security.agent_auth import AgentPrincipal
from app.runtime import get_remote_operation_repository

router = APIRouter(prefix="/api/v1", tags=["remote-operations"])
OperationRepository = Annotated[
    SqlAlchemyRemoteOperationRepository,
    Depends(get_remote_operation_repository),
]
Operator = Annotated[None, Depends(require_operator)]
AuthenticatedAgent = Annotated[AgentPrincipal, Depends(require_agent_principal)]


def _operation_response(operation: RemoteOperation) -> RemoteOperationResponse:
    return RemoteOperationResponse(
        id=operation.id,
        deviceId=operation.device_id,
        agentId=operation.agent_id,
        operationType=operation.operation_type.value,
        status=operation.status.value,
        requestedBy=operation.requested_by,
        createdAt=operation.created_at,
        expiresAt=operation.expires_at,
        arguments=operation.arguments,
        claimedAt=operation.claimed_at,
        completedAt=operation.completed_at,
        result=operation.result,
        error=operation.error,
    )


@router.get(
    "/operator/remote-operations",
    response_model=list[RemoteOperationResponse],
)
def list_remote_operations(
    _: Operator,
    repository: OperationRepository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[RemoteOperationResponse]:
    return [
        _operation_response(operation)
        for operation in repository.list_operations(device_id=device_id, limit=limit)
    ]


@router.post(
    "/operator/remote-operations",
    response_model=RemoteOperationResponse,
    status_code=status.HTTP_201_CREATED,
)
def queue_remote_operation(
    request: RemoteOperationCreateRequest,
    _: Operator,
    repository: OperationRepository,
) -> RemoteOperationResponse:
    try:
        operation = repository.queue(
            device_id=request.deviceId,
            operation_type=RemoteOperationType(request.operationType),
            arguments=request.arguments,
            ttl_seconds=request.ttlSeconds,
        )
    except NoAgentForDeviceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="device has no enrolled agent available for remote operations",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _operation_response(operation)


@router.post(
    "/agents/operations/claim",
    response_model=None,
)
def claim_remote_operation(
    principal: AuthenticatedAgent,
    repository: OperationRepository,
) -> RemoteOperationClaimResponse | Response:
    operation = repository.claim_next(principal.agent_id)
    if operation is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return RemoteOperationClaimResponse(
        id=operation.id,
        operationType=operation.operation_type.value,
        arguments=operation.arguments,
        expiresAt=operation.expires_at,
    )


@router.post(
    "/agents/operations/{operation_id}/complete",
    response_model=RemoteOperationResponse,
)
def complete_remote_operation(
    operation_id: str,
    request: RemoteOperationCompleteRequest,
    principal: AuthenticatedAgent,
    repository: OperationRepository,
) -> RemoteOperationResponse:
    try:
        operation = repository.complete(
            agent_id=principal.agent_id,
            operation_id=operation_id,
            succeeded=request.status == "succeeded",
            result=request.result,
            error=request.error,
        )
    except RemoteOperationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="operation not found") from exc
    except InvalidRemoteOperationTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="operation is not in a claimable completion state",
        ) from exc
    return _operation_response(operation)
