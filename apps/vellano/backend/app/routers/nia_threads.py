from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_nia_threads_service, require_nia_use
from app.schemas.nia import (
    NiaThreadCreate,
    NiaThreadResponse,
    NiaThreadSummaryResponse,
)
from app.services.nia_threads import NiaThreadsService

nia_threads_router = APIRouter(prefix="/api/v1/nia/threads", tags=["nia"])


@nia_threads_router.get("", response_model=list[NiaThreadSummaryResponse])
async def list_nia_threads(
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaThreadsService = Depends(get_nia_threads_service),
) -> list[NiaThreadSummaryResponse]:
    return await service.list_threads(user_id)


@nia_threads_router.post(
    "",
    response_model=NiaThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_nia_thread(
    body: NiaThreadCreate,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaThreadsService = Depends(get_nia_threads_service),
) -> NiaThreadResponse:
    return await service.create_thread(user_id, body)


@nia_threads_router.get("/{thread_id}", response_model=NiaThreadResponse)
async def get_nia_thread(
    thread_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaThreadsService = Depends(get_nia_threads_service),
) -> NiaThreadResponse:
    return await service.get_thread(user_id, thread_id)


@nia_threads_router.post("/{thread_id}/archive", response_model=NiaThreadSummaryResponse)
async def archive_nia_thread(
    thread_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaThreadsService = Depends(get_nia_threads_service),
) -> NiaThreadSummaryResponse:
    return await service.archive_thread(user_id, thread_id)
