from fastapi import APIRouter, Depends, status

from app.api.schemas.agent import HeartbeatRequest, TelemetryRequest
from app.application.use_cases.record_heartbeat import RecordHeartbeat
from app.application.use_cases.record_telemetry import RecordTelemetry
from app.domain.telemetry.models import Metric, TelemetryBatch
from app.runtime import get_heartbeat_use_case, get_telemetry_use_case

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/heartbeat")
def heartbeat(
    request: HeartbeatRequest,
    use_case: RecordHeartbeat = Depends(get_heartbeat_use_case),
) -> dict[str, str]:
    device = use_case.execute(request.agentId, request.timestamp)
    return {"deviceId": device.id, "status": device.status.value}


@router.post("/telemetry", status_code=status.HTTP_202_ACCEPTED)
def telemetry(
    request: TelemetryRequest,
    use_case: RecordTelemetry = Depends(get_telemetry_use_case),
) -> dict[str, str]:
    batch = TelemetryBatch(
        agent_id=request.agentId,
        timestamp=request.timestamp,
        metrics=tuple(Metric(metric.name, metric.value, metric.unit) for metric in request.metrics),
    )
    use_case.execute(batch)
    return {"status": "accepted"}
