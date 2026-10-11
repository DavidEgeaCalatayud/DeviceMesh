from datetime import datetime

from pydantic import BaseModel, Field


class NmsTargetCreate(BaseModel):
    deviceId: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=64)
    port: int = Field(default=161, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=64)
    authSecretRef: str = Field(min_length=1, max_length=128)
    intervalSeconds: int = Field(default=60, ge=15, le=86400)


class NmsTargetResponse(BaseModel):
    id: str
    deviceId: str
    address: str
    port: int
    username: str
    authProtocol: str
    authSecretRef: str
    intervalSeconds: int
    enabled: bool
    lastPolledAt: datetime | None
    lastError: str | None


class NmsTargetStateRequest(BaseModel):
    enabled: bool


class NetworkNeighborResponse(BaseModel):
    deviceId: str
    localInterface: str
    protocol: str
    remoteChassisId: str | None
    remoteSystemName: str | None
    remotePortId: str | None
    remoteDeviceId: str | None
    present: bool
    firstSeen: datetime
    lastSeen: datetime
    lastChangedAt: datetime


class NetworkRouteResponse(BaseModel):
    deviceId: str
    destination: str
    prefixLength: int
    nextHop: str | None
    interfaceName: str | None
    routeType: str | None
    source: str
    present: bool
    firstSeen: datetime
    lastSeen: datetime


class ArpEntryResponse(BaseModel):
    deviceId: str
    interfaceName: str | None
    ipAddress: str
    macAddress: str
    source: str
    present: bool
    firstSeen: datetime
    lastSeen: datetime


class VlanResponse(BaseModel):
    deviceId: str
    vlanId: int
    name: str | None
    source: str
    present: bool
    firstSeen: datetime
    lastSeen: datetime


class InterfaceCounterResponse(BaseModel):
    deviceId: str
    interfaceName: str
    sampledAt: datetime
    inOctets: int | None
    outOctets: int | None
    inErrors: int | None
    outErrors: int | None
