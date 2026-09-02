from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.dependencies.auth import get_nia_run_service, require_nia_use
from app.services.nia_run import NiaRunService

nia_run_router = APIRouter(prefix="/api/v1/nia/threads", tags=["nia"])


@nia_run_router.post("/{thread_id}/run")
async def run_nia_thread(
    thread_id: uuid.UUID,
    request: Request,
    user_id: uuid.UUID = Depends(require_nia_use),
    service: NiaRunService = Depends(get_nia_run_service),
):
    return await service.dispatch_run(
        user_id=user_id,
        thread_id=thread_id,
        request=request,
    )
