from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.security import require_agent_principal
from app.api.schemas.agent import HeartbeatRequest, TelemetryRequest
from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.domain.devices.models import DeviceIdentity
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.infrastructure.security.agent_auth import AgentPrincipal
from app.runtime import get_heartbeat_use_case, get_telemetry_use_case

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

HeartbeatUseCase = Annotated[RecordHeartbeat, Depends(get_heartbeat_use_case)]
TelemetryUseCase = Annotated[RecordTelemetry, Depends(get_telemetry_use_case)]
AuthenticatedAgent = Annotated[AgentPrincipal, Depends(require_agent_principal)]


def _require_matching_agent(principal: AgentPrincipal, payload_agent_id: str) -> None:
    if principal.agent_id != payload_agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="agent identity mismatch")


@router.post("/heartbeat")
def heartbeat(
    request: HeartbeatRequest,
    principal: AuthenticatedAgent,
    use_case: HeartbeatUseCase,
) -> dict[str, str]:
    _require_matching_agent(principal, request.agentId)
    identity = None
    if request.device is not None:
        identity = DeviceIdentity(
            hostname=request.device.hostname,
            operating_system=request.device.operatingSystem,
            operating_system_version=request.device.operatingSystemVersion,
            architecture=request.device.architecture,
            manufacturer=request.device.manufacturer,
            ip_addresses=tuple(request.device.ipAddresses),
            mac_addresses=tuple(request.device.macAddresses),
        )
    device = use_case.execute(request.agentId, request.timestamp, identity)
    return {"deviceId": device.id, "status": device.status.value}


@router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
def telemetry(
    request: TelemetryRequest,
    principal: AuthenticatedAgent,
    use_case: TelemetryUseCase,
) -> dict[str, str]:
    _require_matching_agent(principal, request.agentId)
    batch = TelemetryBatch(
        agent_id=request.agentId,
        timestamp=request.timestamp,
        metrics=tuple(Metric(metric.name, metric.value, metric.unit) for metric in request.metrics),
    )
    use_case.execute(batch)
    return {"status": "accepted"}
