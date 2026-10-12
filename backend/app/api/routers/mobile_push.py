from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies.security import require_human
from app.api.schemas.mobile_push import (
    MobilePushRegistrationRequest,
    MobilePushRegistrationResponse,
)
from app.infrastructure.repositories.mobile_push import (
    SqlAlchemyMobilePushRepository,
)
from app.infrastructure.security.human_auth import HumanPrincipal
from app.runtime import get_mobile_push_repository

router = APIRouter(prefix="/api/v1/mobile", tags=["mobile-push"])
Repository = Annotated[SqlAlchemyMobilePushRepository, Depends(get_mobile_push_repository)]
Human = Annotated[HumanPrincipal, Depends(require_human)]


@router.post(
    "/push-subscriptions",
    response_model=MobilePushRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_push_subscription(
    request: MobilePushRegistrationRequest,
    principal: Human,
    repository: Repository,
) -> MobilePushRegistrationResponse:
    target = repository.register(
        user_id=principal.id,
        provider=request.provider,
        environment=request.environment,
        installation_id=request.installationId,
        token=request.token,
    )
    return MobilePushRegistrationResponse(
        id=target.id,
        provider=target.provider,
        environment=target.environment,
        installationId=target.installation_id,
    )


@router.delete("/push-subscriptions/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_subscription(
    installation_id: str,
    principal: Human,
    repository: Repository,
) -> Response:
    repository.unregister(user_id=principal.id, installation_id=installation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
