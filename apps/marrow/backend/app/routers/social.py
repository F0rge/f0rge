from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.notifications import get_notification_service
from app.dependencies.social import get_social_service
from app.middleware.auth import get_current_session
from app.schemas.social import (
    ConnectionItem,
    ConnectionListResponse,
    ConnectionRequest,
    HandleAvailableResponse,
    PublicUserCard,
)
from app.services.notifications import NotificationService
from app.services.social import SocialService

router = APIRouter(
    prefix="/api/v1/social",
    tags=["social"],
)


@router.get("/handle-available", response_model=HandleAvailableResponse)
async def handle_available(
    handle: str = Query(..., min_length=1),
    service: SocialService = Depends(get_social_service),
):
    available = await service.check_handle_available(handle)
    return HandleAvailableResponse(available=available)


@router.get(
    "/users/lookup",
    response_model=PublicUserCard,
    dependencies=[Depends(get_current_session)],
)
async def lookup_user(
    handle: str = Query(..., min_length=1),
    service: SocialService = Depends(get_social_service),
):
    return await service.lookup_by_handle(handle)


@router.get(
    "/connections",
    response_model=ConnectionListResponse,
    dependencies=[Depends(get_current_session)],
)
async def list_connections(service: SocialService = Depends(get_social_service)):
    return await service.list_connections()


@router.post(
    "/connections",
    response_model=ConnectionItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_session)],
)
async def send_connection(
    body: ConnectionRequest,
    service: SocialService = Depends(get_social_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    return await service.send_connection_request(body.handle, notifications)


@router.post(
    "/connections/{connection_id}/accept",
    response_model=ConnectionItem,
    dependencies=[Depends(get_current_session)],
)
async def accept_connection(
    connection_id: uuid.UUID,
    service: SocialService = Depends(get_social_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    return await service.accept_connection(connection_id, notifications)


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def delete_connection(
    connection_id: uuid.UUID,
    service: SocialService = Depends(get_social_service),
):
    await service.delete_connection(connection_id)
