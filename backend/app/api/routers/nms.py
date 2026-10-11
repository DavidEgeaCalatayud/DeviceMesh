from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.nms import (
    ArpEntryResponse,
    InterfaceCounterResponse,
    NetworkNeighborResponse,
    NetworkRouteResponse,
    NmsTargetCreate,
    NmsTargetResponse,
    NmsTargetStateRequest,
    VlanResponse,
)
from app.infrastructure.nms_secrets import validate_nms_secret_ref
from app.infrastructure.repositories.nms import SqlAlchemyNmsRepository
from app.runtime import get_nms_repository

router = APIRouter(prefix="/api/v1/network", tags=["network"])
operator_router = APIRouter(prefix="/api/v1/operator/network", tags=["network-operator"])
Repository = Annotated[SqlAlchemyNmsRepository, Depends(get_nms_repository)]
Operator = Annotated[None, Depends(require_operator)]


def _target_response(target: object) -> NmsTargetResponse:
    return NmsTargetResponse(
        id=target.id,
        deviceId=target.device_id,
        address=target.address,
        port=target.port,
        username=target.username,
        authProtocol=target.auth_protocol.value,
        authSecretRef=target.auth_secret_ref,
        intervalSeconds=target.interval_seconds,
        enabled=target.enabled,
        lastPolledAt=target.last_polled_at,
        lastError=target.last_error,
    )


@operator_router.post("/targets", response_model=NmsTargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(request: NmsTargetCreate, repository: Repository, _: Operator) -> NmsTargetResponse:
    try:
        validate_nms_secret_ref(request.authSecretRef)
        target = repository.create_target(
            device_id=request.deviceId,
            address=request.address,
            port=request.port,
            username=request.username,
            auth_secret_ref=request.authSecretRef,
            interval_seconds=request.intervalSeconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _target_response(target)


@operator_router.get("/targets", response_model=list[NmsTargetResponse])
def list_targets(repository: Repository, _: Operator) -> list[NmsTargetResponse]:
    return [_target_response(target) for target in repository.list_targets()]


@operator_router.patch("/targets/{target_id}/state", response_model=NmsTargetResponse)
def set_target_state(
    target_id: str,
    request: NmsTargetStateRequest,
    repository: Repository,
    _: Operator,
) -> NmsTargetResponse:
    try:
        return _target_response(repository.set_target_state(target_id, request.enabled))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NMS target not found") from exc


@router.get("/neighbors", response_model=list[NetworkNeighborResponse])
def neighbors(
    repository: Repository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    present_only: Annotated[bool, Query(alias="presentOnly")] = True,
) -> list[NetworkNeighborResponse]:
    return [
        NetworkNeighborResponse(
            deviceId=item.device_id,
            localInterface=item.local_interface,
            protocol=item.protocol,
            remoteChassisId=item.remote_chassis_id,
            remoteSystemName=item.remote_system_name,
            remotePortId=item.remote_port_id,
            remoteDeviceId=item.remote_device_id,
            present=item.present,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
            lastChangedAt=item.last_changed_at,
        )
        for item in repository.list_neighbors(device_id=device_id, present_only=present_only)
    ]


@router.get("/routes", response_model=list[NetworkRouteResponse])
def routes(
    repository: Repository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    present_only: Annotated[bool, Query(alias="presentOnly")] = True,
) -> list[NetworkRouteResponse]:
    return [
        NetworkRouteResponse(
            deviceId=item.device_id,
            destination=item.destination,
            prefixLength=item.prefix_length,
            nextHop=item.next_hop,
            interfaceName=item.interface_name,
            routeType=item.route_type,
            source=item.source,
            present=item.present,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
        )
        for item in repository.list_routes(device_id=device_id, present_only=present_only)
    ]


@router.get("/arp", response_model=list[ArpEntryResponse])
def arp(
    repository: Repository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    present_only: Annotated[bool, Query(alias="presentOnly")] = True,
) -> list[ArpEntryResponse]:
    return [
        ArpEntryResponse(
            deviceId=item.device_id,
            interfaceName=item.interface_name,
            ipAddress=item.ip_address,
            macAddress=item.mac_address,
            source=item.source,
            present=item.present,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
        )
        for item in repository.list_arp(device_id=device_id, present_only=present_only)
    ]


@router.get("/vlans", response_model=list[VlanResponse])
def vlans(
    repository: Repository,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    present_only: Annotated[bool, Query(alias="presentOnly")] = True,
) -> list[VlanResponse]:
    return [
        VlanResponse(
            deviceId=item.device_id,
            vlanId=item.vlan_id,
            name=item.name,
            source=item.source,
            present=item.present,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
        )
        for item in repository.list_vlans(device_id=device_id, present_only=present_only)
    ]


@router.get("/interface-counters", response_model=list[InterfaceCounterResponse])
def interface_counters(
    repository: Repository,
    device_id: Annotated[str, Query(alias="deviceId", min_length=1, max_length=128)],
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[InterfaceCounterResponse]:
    return [
        InterfaceCounterResponse(
            deviceId=item.device_id,
            interfaceName=item.interface_name,
            sampledAt=item.sampled_at,
            inOctets=item.in_octets,
            outOctets=item.out_octets,
            inErrors=item.in_errors,
            outErrors=item.out_errors,
        )
        for item in repository.list_interface_samples(device_id, limit=limit)
    ]
