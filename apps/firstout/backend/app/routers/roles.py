from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_role_service, require_owner
from app.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from app.services.roles import RoleService

roles_router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


@roles_router.get("", response_model=list[RoleResponse])
async def list_roles(
    _: uuid.UUID = Depends(require_owner),
    service: RoleService = Depends(get_role_service),
):
    return await service.list()


@roles_router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    _: uuid.UUID = Depends(require_owner),
    service: RoleService = Depends(get_role_service),
):
    return await service.create(body)


@roles_router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    body: RoleUpdate,
    _: uuid.UUID = Depends(require_owner),
    service: RoleService = Depends(get_role_service),
):
    return await service.update(role_id, body)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: RoleService = Depends(get_role_service),
):
    return await service.delete(role_id)
