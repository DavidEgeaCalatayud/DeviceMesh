from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies.security import get_human_auth_service, require_admin, require_human
from app.infrastructure.security.human_auth import (
    AuditRow,
    AuthenticationError,
    HumanAuthService,
    HumanPrincipal,
    HumanSessionRow,
    LoginThrottled,
    UserRow,
    audit,
)

router = APIRouter(prefix="/api/v1", tags=["human-security"])
Auth = Annotated[HumanAuthService, Depends(get_human_auth_service)]
Admin = Annotated[HumanPrincipal, Depends(require_admin)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=1, max_length=256)


class UserCreate(LoginRequest):
    password: str = Field(min_length=12, max_length=256)
    role: Literal["viewer", "operator", "administrator"]


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=32, max_length=256)


class UserState(BaseModel):
    enabled: bool


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response, auth: Auth) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return auth.login(body.username, body.password,
                          request.client.host if request.client else "unknown",
                          getattr(request.state, "request_id", None))
    except LoginThrottled as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "300"}) from exc
    except AuthenticationError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post("/auth/refresh")
def refresh(body: RefreshRequest, response: Response, auth: Auth) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return auth.refresh(body.refreshToken)
    except AuthenticationError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.get("/auth/me")
def me(principal: Annotated[HumanPrincipal, Depends(require_human)]) -> dict[str, str]:
    return {"id": principal.id, "username": principal.username, "role": principal.role}


@router.post("/auth/logout", status_code=204)
def logout(principal: Annotated[HumanPrincipal, Depends(require_human)], auth: Auth) -> Response:
    auth.logout(principal)
    return Response(status_code=204)


@router.post("/admin/users", status_code=201)
def create_user(body: UserCreate, admin: Admin, auth: Auth) -> dict[str, str]:
    try:
        user = auth.create_user(body.username, body.password, body.role, admin.id)
        return {"id": user.id, "username": user.username, "role": user.role}
    except IntegrityError as exc:
        raise HTTPException(409, "username already exists") from exc


@router.get("/admin/users")
def list_users(admin: Admin, auth: Auth, limit: Annotated[int, Query(ge=1, le=200)] = 100) -> list[dict[str, object]]:
    with auth.sessions() as session:
        return [{"id": u.id, "username": u.username, "role": u.role, "enabled": u.enabled}
                for u in session.scalars(select(UserRow).order_by(UserRow.username).limit(limit))]


@router.patch("/admin/users/{user_id}")
def disable_user(user_id: str, body: UserState, admin: Admin, auth: Auth) -> dict[str, object]:
    if user_id == admin.id and not body.enabled:
        raise HTTPException(409, "cannot disable your own account")
    with auth.sessions.begin() as session:
        user = session.get(UserRow, user_id)
        if not user:
            raise HTTPException(404, "user not found")
        user.enabled = body.enabled
        if not body.enabled:
            session.execute(update(HumanSessionRow).where(
                HumanSessionRow.user_id == user_id).values(revoked_at=datetime.now(UTC)))
        audit(session, admin.id, "user.state_changed", user_id, {"enabled": body.enabled})
    return {"id": user_id, "enabled": body.enabled}


@router.get("/admin/audit-log")
def audit_log(admin: Admin, auth: Auth, limit: Annotated[int, Query(ge=1, le=200)] = 100,
              offset: Annotated[int, Query(ge=0, le=100000)] = 0) -> list[dict[str, object]]:
    with auth.sessions() as session:
        return [{"id": r.id, "actor": r.actor, "action": r.action, "resource": r.resource,
                 "timestamp": r.timestamp, "sourceIp": r.source_ip,
                 "requestId": r.request_id, "metadata": r.details}
                for r in session.scalars(select(AuditRow).order_by(AuditRow.timestamp.desc(), AuditRow.id)
                                         .limit(limit).offset(offset))]
