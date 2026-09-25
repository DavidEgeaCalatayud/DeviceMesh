from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from starlette.requests import HTTPConnection

from app.core.config import get_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.security.agent_auth import (
    AgentAuthenticationError,
    AgentAuthService,
    AgentPrincipal,
    AgentReplayError,
)
from app.infrastructure.security.human_auth import (
    AuthenticationError,
    HumanAuthService,
    HumanPrincipal,
)
from app.runtime import get_agent_auth_service

AgentAuthServiceDependency = Annotated[AgentAuthService, Depends(get_agent_auth_service)]


@lru_cache
def get_human_auth_service() -> HumanAuthService:
    return HumanAuthService(SessionFactory, get_settings())


def require_human(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> HumanPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "human authentication required")
    try:
        return get_human_auth_service().authenticate(authorization[7:])
    except AuthenticationError as exc:
        raise HTTPException(401, str(exc)) from exc


def require_operator(
    principal: Annotated[HumanPrincipal, Depends(require_human)],
) -> HumanPrincipal:
    if principal.role not in {"operator", "administrator"}:
        raise HTTPException(403, "operator role required")
    return principal


def require_admin(
    principal: Annotated[HumanPrincipal, Depends(require_human)],
) -> HumanPrincipal:
    if principal.role != "administrator":
        raise HTTPException(403, "administrator role required")
    return principal


def require_read_access(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    if not get_settings().public_reads:
        require_human(authorization)


def human_access_gate(request: HTTPConnection) -> None:
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return
    if path in {"/api/v1/auth/login", "/api/v1/auth/refresh"}:
        return
    if path.startswith(("/api/v1/agents/", "/api/v1/probes/")):
        return  # Machine endpoints enforce their own independent credentials.
    authorization = request.headers.get("Authorization")
    if path.startswith("/api/v1/discovery/") and authorization and authorization.startswith("Probe "):
        from app.infrastructure.repositories.synthetics import SyntheticProbeAuthenticationError
        from app.runtime import get_synthetic_repository
        try:
            probe = get_synthetic_repository().authenticate_probe(authorization[6:])
        except SyntheticProbeAuthenticationError as exc:
            raise HTTPException(401, "invalid discovery probe credential") from exc
        request.state.actor = f"probe:{probe.id}"
        return
    if get_settings().public_reads and not authorization:
        return  # Explicit compatibility mode for local development only.
    principal = require_human(authorization)
    request.state.actor = principal.id
    if path.startswith("/api/v1/discovery/") and principal.role == "viewer":
        raise HTTPException(403, "operator role required")


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
