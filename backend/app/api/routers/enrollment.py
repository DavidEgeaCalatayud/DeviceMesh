from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies.security import require_operator
from app.api.schemas.enrollment import (
    AgentCredentialResponse,
    AgentEnrollmentRequest,
    EnrollmentTokenCreateRequest,
    EnrollmentTokenResponse,
)
from app.infrastructure.security.agent_auth import (
    AgentAuthService,
    AgentCredentialNotFoundError,
    EnrollmentTokenInvalidError,
    EnrollmentTokenUsedError,
)
from app.runtime import get_agent_auth_service

router = APIRouter(prefix="/api/v1", tags=["agent-security"])
AuthService = Annotated[AgentAuthService, Depends(get_agent_auth_service)]
Operator = Annotated[None, Depends(require_operator)]


@router.post("/operator/agent-enrollment-tokens", response_model=EnrollmentTokenResponse)
def create_enrollment_token(
    request: EnrollmentTokenCreateRequest,
    _: Operator,
    service: AuthService,
) -> EnrollmentTokenResponse:
    issued = service.create_enrollment_token(request.ttlSeconds)
    return EnrollmentTokenResponse(token=issued.token, expiresAt=issued.expires_at)


@router.post("/agents/enroll", response_model=AgentCredentialResponse)
def enroll_agent(request: AgentEnrollmentRequest, service: AuthService) -> AgentCredentialResponse:
    try:
        issued = service.enroll(request.token, request.agentId)
    except EnrollmentTokenUsedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="enrollment token already used") from exc
    except EnrollmentTokenInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired enrollment token") from exc
    return AgentCredentialResponse(
        agentId=issued.agent_id,
        credentialId=issued.credential_id,
        credential=issued.credential,
    )


@router.post("/operator/agents/{agent_id}/credentials/rotate", response_model=AgentCredentialResponse)
def rotate_agent_credential(
    agent_id: str,
    _: Operator,
    service: AuthService,
) -> AgentCredentialResponse:
    issued = service.rotate(agent_id)
    return AgentCredentialResponse(
        agentId=issued.agent_id,
        credentialId=issued.credential_id,
        credential=issued.credential,
    )


@router.delete("/operator/agents/{agent_id}/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_agent_credential(
    agent_id: str,
    credential_id: str,
    _: Operator,
    service: AuthService,
) -> Response:
    try:
        service.revoke(agent_id, credential_id)
    except AgentCredentialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credential not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
