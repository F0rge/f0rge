from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_nia_schedule_service, require_nia_use
from app.schemas.nia import (
    NiaScheduledTaskCreate,
    NiaScheduledTaskResponse,
    NiaScheduledTaskUpdate,
)
from app.services.nia_schedule import NiaScheduleService

nia_schedule_router = APIRouter(prefix="/api/v1/nia/schedule", tags=["nia"])


@nia_schedule_router.get("", response_model=list[NiaScheduledTaskResponse])
async def list_scheduled_tasks(
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> list[NiaScheduledTaskResponse]:
    return await service.list_tasks(user_id)


@nia_schedule_router.post(
    "",
    response_model=NiaScheduledTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scheduled_task(
    body: NiaScheduledTaskCreate,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> NiaScheduledTaskResponse:
    return await service.create_task(user_id, body)


@nia_schedule_router.get("/{task_id}", response_model=NiaScheduledTaskResponse)
async def get_scheduled_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> NiaScheduledTaskResponse:
    return await service.get_task(user_id, task_id)


@nia_schedule_router.patch("/{task_id}", response_model=NiaScheduledTaskResponse)
async def update_scheduled_task(
    task_id: uuid.UUID,
    body: NiaScheduledTaskUpdate,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> NiaScheduledTaskResponse:
    return await service.update_task(user_id, task_id, body)


@nia_schedule_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> None:
    await service.delete_task(user_id, task_id)


@nia_schedule_router.post("/{task_id}/run", response_model=NiaScheduledTaskResponse)
async def run_scheduled_task_now(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaScheduleService = Depends(get_nia_schedule_service),
) -> NiaScheduledTaskResponse:
    return await service.run_now(user_id, task_id)
