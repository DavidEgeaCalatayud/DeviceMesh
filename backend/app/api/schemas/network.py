from datetime import datetime

from pydantic import BaseModel


class DeviceServiceResponse(BaseModel):
    deviceId: str
    port: int
    transport: str
    name: str | None
    state: str
    firstSeen: datetime
    lastSeen: datetime
    lastChangedAt: datetime
    source: str
    networkCidr: str | None


class NetworkInterfaceResponse(BaseModel):
    deviceId: str
    name: str
    macAddress: str | None
    operationalStatus: str
    mtu: int | None
    speedBps: int | None
    vlanId: int | None
    ipAddresses: list[str]
    gateways: list[str]
    dnsServers: list[str]
    source: str
    present: bool
    firstSeen: datetime
    lastSeen: datetime
    lastChangedAt: datetime


class TopologyNodeResponse(BaseModel):
    id: str
    kind: str
    label: str
    deviceId: str | None
    networkCidr: str | None
    status: str | None


class TopologyEdgeResponse(BaseModel):
    source: str
    target: str
    relation: str


class NetworkTopologyResponse(BaseModel):
    nodes: list[TopologyNodeResponse]
    edges: list[TopologyEdgeResponse]
    method: str
    approximate: bool
