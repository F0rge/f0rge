from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_profile_service,
    get_user_service,
    require_owner,
    get_current_user_id,
)
from app.schemas.user import ProfileUpdate, UserCreate, UserResponse, UserUpdate
from app.services.users import ProfileService, UserService

users_router = APIRouter(prefix="/api/v1/users", tags=["users"])
profile_router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@users_router.get("", response_model=list[UserResponse])
async def list_users(
    _: uuid.UUID = Depends(require_owner),
    service: UserService = Depends(get_user_service),
):
    return await service.list()


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    _: uuid.UUID = Depends(require_owner),
    service: UserService = Depends(get_user_service),
):
    return await service.create(body)


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    _: uuid.UUID = Depends(require_owner),
    service: UserService = Depends(get_user_service),
):
    return await service.update(user_id, body)


@profile_router.patch("", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.update(user_id, body)
