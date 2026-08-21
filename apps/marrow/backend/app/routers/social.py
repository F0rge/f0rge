from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.dependencies.groups import get_group_service
from app.dependencies.meal_tags import get_meal_tag_service
from app.dependencies.notifications import get_notification_service
from app.dependencies.social import get_social_service
from app.middleware.auth import get_current_session
from app.schemas.social import (
    ConnectionItem,
    ConnectionListResponse,
    ConnectionRequest,
    GroupCreate,
    GroupDetailResponse,
    GroupInviteRequest,
    GroupListItem,
    GroupListResponse,
    GroupMemberItem,
    GroupRename,
    HandleAvailableResponse,
    MealTagListResponse,
    PublicUserCard,
    UserSearchResponse,
)
from app.services.groups import GroupService
from app.services.meal_tags import MealTagService
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
    return await service.describe_handle_available(handle)


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
    "/users/{handle}/avatar",
    response_model=None,
    dependencies=[Depends(get_current_session)],
)
async def peer_avatar(
    handle: str,
    service: SocialService = Depends(get_social_service),
) -> Response:
    return await service.serve_peer_avatar_response(handle)


@router.get(
    "/users/search",
    response_model=UserSearchResponse,
    dependencies=[Depends(get_current_session)],
)
async def search_users(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    service: SocialService = Depends(get_social_service),
):
    return await service.search_users(q, limit)


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


@router.post(
    "/groups",
    response_model=GroupListItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_session)],
)
async def create_group(
    body: GroupCreate,
    service: GroupService = Depends(get_group_service),
):
    return await service.create_group(body)


@router.get(
    "/groups",
    response_model=GroupListResponse,
    dependencies=[Depends(get_current_session)],
)
async def list_groups(service: GroupService = Depends(get_group_service)):
    return await service.list_groups()


@router.get(
    "/groups/{group_id}",
    response_model=GroupDetailResponse,
    dependencies=[Depends(get_current_session)],
)
async def get_group(
    group_id: uuid.UUID,
    service: GroupService = Depends(get_group_service),
):
    return await service.get_group(group_id)


@router.patch(
    "/groups/{group_id}",
    response_model=GroupListItem,
    dependencies=[Depends(get_current_session)],
)
async def rename_group(
    group_id: uuid.UUID,
    body: GroupRename,
    service: GroupService = Depends(get_group_service),
):
    return await service.rename_group(group_id, body)


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def delete_group(
    group_id: uuid.UUID,
    service: GroupService = Depends(get_group_service),
):
    await service.delete_group(group_id)


@router.post(
    "/groups/{group_id}/invite",
    response_model=GroupMemberItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_session)],
)
async def invite_to_group(
    group_id: uuid.UUID,
    body: GroupInviteRequest,
    service: GroupService = Depends(get_group_service),
    social: SocialService = Depends(get_social_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    return await service.invite_to_group(group_id, body, social, notifications)


@router.post(
    "/groups/{group_id}/accept",
    response_model=GroupMemberItem,
    dependencies=[Depends(get_current_session)],
)
async def accept_group_invite(
    group_id: uuid.UUID,
    service: GroupService = Depends(get_group_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    return await service.accept_group_invite(group_id, notifications)


@router.post(
    "/groups/{group_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def decline_group_invite(
    group_id: uuid.UUID,
    service: GroupService = Depends(get_group_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    await service.decline_group_invite(group_id, notifications)


@router.delete(
    "/groups/{group_id}/members/{handle}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def remove_group_member(
    group_id: uuid.UUID,
    handle: str,
    service: GroupService = Depends(get_group_service),
    notifications: NotificationService = Depends(get_notification_service),
):
    await service.remove_member(group_id, handle, notifications)


@router.get(
    "/meal-tags",
    response_model=MealTagListResponse,
    dependencies=[Depends(get_current_session)],
)
async def list_meal_tags(service: MealTagService = Depends(get_meal_tag_service)):
    return await service.list_tags()


@router.post(
    "/meal-tags/{tag_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def approve_meal_tag(
    tag_id: uuid.UUID,
    service: MealTagService = Depends(get_meal_tag_service),
):
    await service.approve(tag_id)


@router.post(
    "/meal-tags/{tag_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def decline_meal_tag(
    tag_id: uuid.UUID,
    service: MealTagService = Depends(get_meal_tag_service),
):
    await service.decline(tag_id)


@router.delete(
    "/meal-tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_session)],
)
async def cancel_meal_tag(
    tag_id: uuid.UUID,
    service: MealTagService = Depends(get_meal_tag_service),
):
    await service.cancel(tag_id)
