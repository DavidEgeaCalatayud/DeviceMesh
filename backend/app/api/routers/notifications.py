from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.security import require_operator
from app.api.schemas.notifications import (
    NotificationChannelCreateRequest,
    NotificationChannelResponse,
    NotificationDeliveryResponse,
    NotificationRouteCreateRequest,
    NotificationRouteResponse,
    NotificationStateRequest,
)
from app.domain.alerts.notifications import (
    NotificationChannel,
    NotificationChannelKind,
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationRoute,
    NotificationTransitionFilter,
)
from app.infrastructure.repositories.notifications import SqlAlchemyNotificationRepository
from app.runtime import get_notification_repository

router = APIRouter(prefix="/api/v1/operator", tags=["notifications"])
Repository = Annotated[SqlAlchemyNotificationRepository, Depends(get_notification_repository)]
Operator = Annotated[None, Depends(require_operator)]


def _channel_response(channel: NotificationChannel) -> NotificationChannelResponse:
    return NotificationChannelResponse(
        id=channel.id,
        name=channel.name,
        kind=channel.kind.value,
        secretRef=channel.secret_ref,
        config=channel.config,
        enabled=channel.enabled,
    )


def _route_response(route: NotificationRoute) -> NotificationRouteResponse:
    return NotificationRouteResponse(
        id=route.id,
        name=route.name,
        channelId=route.channel_id,
        transition=route.transition.value,
        metricName=route.metric_name,
        deviceId=route.device_id,
        enabled=route.enabled,
    )


def _delivery_response(delivery: NotificationDelivery) -> NotificationDeliveryResponse:
    return NotificationDeliveryResponse(
        id=delivery.id,
        channelId=delivery.channel_id,
        routeId=delivery.route_id,
        alertId=delivery.alert_id,
        transition=delivery.transition,
        status=delivery.status.value,
        attempts=delivery.attempts,
        nextAttemptAt=delivery.next_attempt_at,
        lastAttemptAt=delivery.last_attempt_at,
        deliveredAt=delivery.delivered_at,
        lastError=delivery.last_error,
        payload=delivery.payload,
    )


@router.get("/notification-channels", response_model=list[NotificationChannelResponse])
def list_notification_channels(
    _: Operator,
    repository: Repository,
) -> list[NotificationChannelResponse]:
    return [_channel_response(channel) for channel in repository.list_channels()]


@router.post(
    "/notification-channels",
    response_model=NotificationChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification_channel(
    request: NotificationChannelCreateRequest,
    _: Operator,
    repository: Repository,
) -> NotificationChannelResponse:
    try:
        channel = repository.create_channel(
            name=request.name.strip(),
            kind=NotificationChannelKind(request.kind),
            secret_ref=request.secretRef,
            config=request.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _channel_response(channel)


@router.patch(
    "/notification-channels/{channel_id}/state",
    response_model=NotificationChannelResponse,
)
def set_notification_channel_state(
    channel_id: int,
    request: NotificationStateRequest,
    _: Operator,
    repository: Repository,
) -> NotificationChannelResponse:
    try:
        channel = repository.set_channel_enabled(channel_id, request.enabled)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _channel_response(channel)


@router.get("/notification-routes", response_model=list[NotificationRouteResponse])
def list_notification_routes(
    _: Operator,
    repository: Repository,
) -> list[NotificationRouteResponse]:
    return [_route_response(route) for route in repository.list_routes()]


@router.post(
    "/notification-routes",
    response_model=NotificationRouteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notification_route(
    request: NotificationRouteCreateRequest,
    _: Operator,
    repository: Repository,
) -> NotificationRouteResponse:
    try:
        route = repository.create_route(
            name=request.name.strip(),
            channel_id=request.channelId,
            transition=NotificationTransitionFilter(request.transition),
            metric_name=request.metricName,
            device_id=request.deviceId,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _route_response(route)


@router.patch(
    "/notification-routes/{route_id}/state",
    response_model=NotificationRouteResponse,
)
def set_notification_route_state(
    route_id: int,
    request: NotificationStateRequest,
    _: Operator,
    repository: Repository,
) -> NotificationRouteResponse:
    try:
        route = repository.set_route_enabled(route_id, request.enabled)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _route_response(route)


@router.get("/notification-deliveries", response_model=list[NotificationDeliveryResponse])
def list_notification_deliveries(
    _: Operator,
    repository: Repository,
    delivery_status: Annotated[
        Literal["queued", "delivered", "dead"] | None,
        Query(alias="status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[NotificationDeliveryResponse]:
    status_filter = (
        NotificationDeliveryStatus(delivery_status) if delivery_status is not None else None
    )
    return [
        _delivery_response(delivery)
        for delivery in repository.list_deliveries(status=status_filter, limit=limit)
    ]


@router.post(
    "/notification-deliveries/{delivery_id}/retry",
    response_model=NotificationDeliveryResponse,
)
def retry_notification_delivery(
    delivery_id: int,
    _: Operator,
    repository: Repository,
) -> NotificationDeliveryResponse:
    try:
        delivery = repository.retry_delivery(delivery_id, datetime.now(UTC))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _delivery_response(delivery)
