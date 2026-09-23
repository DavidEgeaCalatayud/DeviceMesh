from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.infrastructure.security.agent_auth import (
    AgentAuthenticationError,
    AgentAuthService,
    AgentPrincipal,
    AgentReplayError,
)
from app.runtime import get_agent_auth_service

AgentAuthServiceDependency = Annotated[AgentAuthService, Depends(get_agent_auth_service)]


def require_operator(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    expected = f"Bearer {get_settings().operator_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="operator authentication required",
        )


def require_agent_principal(
    service: AgentAuthServiceDependency,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    agent_id: Annotated[str | None, Header(alias="X-DeviceMesh-Agent-ID")] = None,
    timestamp: Annotated[str | None, Header(alias="X-DeviceMesh-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-DeviceMesh-Nonce")] = None,
) -> AgentPrincipal:
    if not authorization or not authorization.startswith("Agent "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="agent authentication required",
        )
    if not agent_id or not timestamp or not nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="agent authentication headers required",
        )
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp)
        if parsed_timestamp.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        return service.authenticate(agent_id, authorization[6:], parsed_timestamp, nonce)
    except AgentReplayError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="replayed agent request",
        ) from exc
    except (AgentAuthenticationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid agent authentication",
        ) from exc
