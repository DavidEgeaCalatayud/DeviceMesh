from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.schemas.network import (
    DeviceServiceResponse,
    NetworkInterfaceResponse,
    NetworkTopologyResponse,
    TopologyEdgeResponse,
    TopologyNodeResponse,
)
from app.infrastructure.repositories.network import SqlAlchemyNetworkRepository
from app.runtime import get_network_repository

router = APIRouter(prefix="/api/v1", tags=["network"])
NetworkRepositoryDependency = Annotated[
    SqlAlchemyNetworkRepository,
    Depends(get_network_repository),
]


@router.get("/services", response_model=list[DeviceServiceResponse])
def list_services(
    repository: NetworkRepositoryDependency,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
) -> list[DeviceServiceResponse]:
    return [
        DeviceServiceResponse(
            deviceId=service.device_id,
            port=service.port,
            transport=service.transport,
            name=service.name,
            state=service.state.value,
            firstSeen=service.first_seen,
            lastSeen=service.last_seen,
            lastChangedAt=service.last_changed_at,
            source=service.source,
            networkCidr=service.network_cidr,
        )
        for service in repository.list_services(
            device_id=device_id,
            active_only=active_only,
        )
    ]


@router.get("/network/interfaces", response_model=list[NetworkInterfaceResponse])
def list_network_interfaces(
    repository: NetworkRepositoryDependency,
    device_id: Annotated[str | None, Query(alias="deviceId")] = None,
    present_only: Annotated[bool, Query(alias="presentOnly")] = True,
) -> list[NetworkInterfaceResponse]:
    return [
        NetworkInterfaceResponse(
            deviceId=item.device_id,
            name=item.name,
            macAddress=item.mac_address,
            operationalStatus=item.operational_status.value,
            mtu=item.mtu,
            speedBps=item.speed_bps,
            vlanId=item.vlan_id,
            ipAddresses=list(item.ip_addresses),
            gateways=list(item.gateways),
            dnsServers=list(item.dns_servers),
            source=item.source,
            present=item.present,
            firstSeen=item.first_seen,
            lastSeen=item.last_seen,
            lastChangedAt=item.last_changed_at,
        )
        for item in repository.list_interfaces(
            device_id=device_id,
            present_only=present_only,
        )
    ]


@router.get("/network/topology", response_model=NetworkTopologyResponse)
def topology(repository: NetworkRepositoryDependency) -> NetworkTopologyResponse:
    result = repository.get_topology()
    return NetworkTopologyResponse(
        nodes=[
            TopologyNodeResponse(
                id=node.id,
                kind=node.kind,
                label=node.label,
                deviceId=node.device_id,
                networkCidr=node.network_cidr,
                status=node.status,
            )
            for node in result.nodes
        ],
        edges=[
            TopologyEdgeResponse(
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
            )
            for edge in result.edges
        ],
        method=result.method,
        approximate=result.approximate,
    )
