from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies.security import require_operator
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.platform import PlatformRepository
from app.infrastructure.security.human_auth import HumanPrincipal

router = APIRouter(prefix="/api/v1", tags=["platform"])
Operator = Annotated[HumanPrincipal, Depends(require_operator)]


def get_platform_repository() -> PlatformRepository:
    return PlatformRepository(SessionFactory)


Repository = Annotated[PlatformRepository, Depends(get_platform_repository)]


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2048)
    owner: str = Field(default="", max_length=128)
    environment: str = Field(default="production", min_length=1, max_length=64)
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(default_factory=list, max_length=32)
    deviceId: str | None = Field(default=None, max_length=128)


class ServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    owner: str | None = Field(default=None, max_length=128)
    environment: str | None = Field(default=None, min_length=1, max_length=64)
    criticality: Literal["low", "medium", "high", "critical"] | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] | None = Field(default=None, max_length=32)
    deviceId: str | None = Field(default=None, max_length=128)


class ServiceGroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2048)
    owner: str = Field(default="", max_length=128)
    environment: str = Field(default="production", min_length=1, max_length=64)
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(default_factory=list, max_length=32)


class MembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True


class DependencyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["hard", "soft"] = "hard"


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"] | None = None
    status: Literal["open", "acknowledged", "investigating", "mitigated", "resolved"] | None = None
    assignedTo: str | None = Field(default=None, max_length=128)
    rootCause: str | None = Field(default=None, max_length=10000)
    resolution: str | None = Field(default=None, max_length=10000)
    impactSummary: str | None = Field(default=None, max_length=10000)
    postmortem: str | None = Field(default=None, max_length=20000)
    note: str | None = Field(default=None, min_length=1, max_length=10000)
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] | None = Field(default=None, max_length=32)


class SloCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=255)
    monitorId: str = Field(min_length=1, max_length=36)
    targetPercent: float = Field(gt=0, lt=100)
    windowDays: Literal[7, 30, 90] = 30
    sliMode: Literal["checks", "time"] = "checks"


@router.get("/service-catalog")
def list_services(repository: Repository, limit: Annotated[int, Query(ge=1, le=200)] = 100,
                  offset: Annotated[int, Query(ge=0, le=100000)] = 0,
                  search: Annotated[str, Query(max_length=128)] = "") -> list[dict[str, object]]:
    return repository.list_services(limit, offset, search)


@router.post("/service-catalog", status_code=201)
def create_service(body: ServiceCreate, operator: Operator, repository: Repository) -> dict[str, object]:
    try:
        return repository.create_service(body.model_dump(), operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/service-catalog/{service_id}")
def update_service(service_id: str, body: ServiceUpdate, operator: Operator,
                   repository: Repository) -> dict[str, object]:
    try:
        return repository.update_service(service_id, body.model_dump(exclude_unset=True), operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/service-catalog/{service_id}/monitors/{monitor_id}")
def link_monitor(service_id: str, monitor_id: str, operator: Operator, repository: Repository) -> dict[str, str]:
    try:
        repository.link_monitor(service_id, monitor_id, operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "linked"}


@router.put("/service-catalog/{service_id}/dependencies/{dependency_id}")
def set_dependency(service_id: str, dependency_id: str, body: DependencyUpdate,
                   operator: Operator, repository: Repository) -> dict[str, str]:
    try:
        repository.set_dependency(service_id, dependency_id, body.kind, operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "linked", "kind": body.kind}


@router.delete("/service-catalog/{service_id}/dependencies/{dependency_id}", status_code=204)
def remove_dependency(service_id: str, dependency_id: str, operator: Operator,
                      repository: Repository) -> Response:
    try:
        repository.remove_dependency(service_id, dependency_id, operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=204)


@router.get("/service-groups")
def list_groups(repository: Repository, limit: Annotated[int, Query(ge=1, le=200)] = 100,
                offset: Annotated[int, Query(ge=0, le=100000)] = 0) -> list[dict[str, object]]:
    return repository.list_groups(limit, offset)


@router.post("/service-groups", status_code=201)
def create_group(body: ServiceGroupCreate, operator: Operator,
                 repository: Repository) -> dict[str, object]:
    return repository.create_group(body.model_dump(), operator.id)


@router.put("/service-groups/{group_id}/services/{service_id}")
def set_group_membership(group_id: str, service_id: str, body: MembershipUpdate,
                         operator: Operator, repository: Repository) -> dict[str, object]:
    try:
        repository.set_group_membership(group_id, service_id, body.enabled, operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"groupId": group_id, "serviceId": service_id, "enabled": body.enabled}


@router.get("/incidents")
def list_incidents(repository: Repository, limit: Annotated[int, Query(ge=1, le=200)] = 100,
                   offset: Annotated[int, Query(ge=0, le=100000)] = 0,
                   activeOnly: bool = False) -> list[dict[str, object]]:
    return repository.list_incidents(limit, offset, activeOnly)


@router.get("/incidents/{incident_id}")
def incident_detail(incident_id: str, repository: Repository) -> dict[str, object]:
    try:
        return repository.incident_detail(incident_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/incidents/{incident_id}")
def update_incident(incident_id: str, body: IncidentUpdate, operator: Operator, repository: Repository) -> dict[str, object]:
    try:
        return repository.update_incident(incident_id, body.model_dump(exclude_none=True), operator.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/service-catalog/{service_id}/slos", status_code=201)
def create_slo(service_id: str, body: SloCreate, operator: Operator, repository: Repository) -> dict[str, str]:
    try:
        return {"id": repository.create_slo(service_id, body.model_dump(), operator.id)}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/service-catalog/{service_id}/slos")
def slo_reports(service_id: str, repository: Repository) -> list[dict[str, object]]:
    try:
        return repository.slo_reports(service_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
