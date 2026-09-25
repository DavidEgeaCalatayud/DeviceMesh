import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Select

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


def _audit_query(
    *,
    actor: str,
    action: str,
    resource: str,
    search: str,
    source_ip: str,
    request_id: str,
    since: datetime | None,
    until: datetime | None,
) -> Select[AuditRow]:
    query = select(AuditRow)
    if actor:
        query = query.where(AuditRow.actor == actor)
    if action:
        query = query.where(AuditRow.action == action)
    if resource:
        query = query.where(AuditRow.resource.icontains(resource, autoescape=True))
    if source_ip:
        query = query.where(AuditRow.source_ip == source_ip)
    if request_id:
        query = query.where(AuditRow.request_id == request_id)
    if search:
        query = query.where(or_(
            AuditRow.actor.icontains(search, autoescape=True),
            AuditRow.action.icontains(search, autoescape=True),
            AuditRow.resource.icontains(search, autoescape=True),
        ))
    if since is not None:
        query = query.where(AuditRow.timestamp >= since)
    if until is not None:
        query = query.where(AuditRow.timestamp <= until)
    return query.order_by(AuditRow.timestamp.desc(), AuditRow.id)


def _audit_view(row: AuditRow) -> dict[str, object]:
    return {"id": row.id, "actor": row.actor, "action": row.action, "resource": row.resource,
            "timestamp": row.timestamp, "sourceIp": row.source_ip,
            "requestId": row.request_id, "metadata": row.details}


@router.get("/admin/audit-log")
def audit_log(
    admin: Admin,
    auth: Auth,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    actor: Annotated[str, Query(max_length=128)] = "",
    action: Annotated[str, Query(max_length=128)] = "",
    resource: Annotated[str, Query(max_length=256)] = "",
    search: Annotated[str, Query(max_length=256)] = "",
    sourceIp: Annotated[str, Query(max_length=64)] = "",
    requestId: Annotated[str, Query(max_length=64)] = "",
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, object]]:
    del admin
    if since is not None and until is not None and since > until:
        raise HTTPException(422, "since must be before until")
    query = _audit_query(actor=actor, action=action, resource=resource, search=search,
                         source_ip=sourceIp, request_id=requestId, since=since, until=until)
    with auth.sessions() as session:
        return [_audit_view(row) for row in session.scalars(query.limit(limit).offset(offset))]


@router.get("/admin/audit-log.csv")
def export_audit_log(
    admin: Admin,
    auth: Auth,
    actor: Annotated[str, Query(max_length=128)] = "",
    action: Annotated[str, Query(max_length=128)] = "",
    resource: Annotated[str, Query(max_length=256)] = "",
    search: Annotated[str, Query(max_length=256)] = "",
    sourceIp: Annotated[str, Query(max_length=64)] = "",
    requestId: Annotated[str, Query(max_length=64)] = "",
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    del admin
    if since is not None and until is not None and since > until:
        raise HTTPException(422, "since must be before until")
    query = _audit_query(actor=actor, action=action, resource=resource, search=search,
                         source_ip=sourceIp, request_id=requestId, since=since, until=until)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "actor", "action", "resource", "source_ip", "request_id", "metadata"])
    with auth.sessions() as session:
        for row in session.scalars(query.limit(10000)):
            writer.writerow([row.timestamp.isoformat(), row.actor, row.action, row.resource,
                             row.source_ip or "", row.request_id or "", str(row.details)])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="devicemesh-audit-log.csv"',
                 "Cache-Control": "no-store"},
    )
