from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.notifications import get_notification_service
from app.middleware.auth import get_current_session
from app.schemas.notifications import (
    MarkReadRequest,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notifications import NotificationService

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = Query(30, ge=1, le=100),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.list_notifications(limit)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(service: NotificationService = Depends(get_notification_service)):
    count = await service.unread_count()
    return UnreadCountResponse(count=count)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    body: MarkReadRequest,
    service: NotificationService = Depends(get_notification_service),
):
    await service.mark_read(body.ids, body.all)
