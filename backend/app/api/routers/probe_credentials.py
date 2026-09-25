from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies.security import require_admin
from app.infrastructure.database import SessionFactory
from app.infrastructure.repositories.synthetics import SyntheticProbeNotFoundError
from app.infrastructure.security.probe_credentials import ProbeCredentialService

router = APIRouter(prefix="/api/v1/operator/synthetic-probes", tags=["synthetics"])
Admin = Annotated[None, Depends(require_admin)]


class ProbeCredentialRotationResponse(BaseModel):
    probeId: str
    token: str
    rotatedAt: str


@router.post("/{probe_id}/rotate-token", response_model=ProbeCredentialRotationResponse)
def rotate_probe_token(probe_id: str, _: Admin) -> ProbeCredentialRotationResponse:
    try:
        rotated = ProbeCredentialService(SessionFactory).rotate(probe_id)
    except SyntheticProbeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="probe not found") from exc
    return ProbeCredentialRotationResponse(
        probeId=rotated.probe_id,
        token=rotated.token,
        rotatedAt=rotated.rotated_at.isoformat(),
    )
