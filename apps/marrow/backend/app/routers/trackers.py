from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.trackers import get_tracker_service
from app.middleware.auth import get_current_session
from app.schemas.tracker import (
    OrderRequest,
    TrackerCreate,
    TrackerResponse,
    TrackerUpdate,
    TrackerValueResponse,
    TrackerValueUpsert,
)
from app.services.trackers import TrackerService

router = APIRouter(
    prefix="/api/v1",
    tags=["trackers"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/trackers", response_model=list[TrackerResponse])
async def list_trackers(
    include_archived: bool = Query(False),
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.list_trackers(include_archived=include_archived)


@router.post("/trackers", response_model=TrackerResponse, status_code=status.HTTP_201_CREATED)
async def create_tracker(
    body: TrackerCreate,
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.create_tracker(body)


@router.patch("/trackers/reorder", response_model=list[TrackerResponse])
async def reorder_trackers(
    body: OrderRequest,
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.reorder_trackers(body.order)


@router.patch("/trackers/{tracker_id}", response_model=TrackerResponse)
async def update_tracker(
    tracker_id: int,
    body: TrackerUpdate,
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.update_tracker(tracker_id, body)


@router.get("/entries/{date}/tracker_values", response_model=list[TrackerValueResponse])
async def list_tracker_values(
    date: datetime.date,
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.list_tracker_values(date)


@router.put(
    "/entries/{date}/tracker_values/{tracker_id}",
    response_model=TrackerValueResponse,
)
async def upsert_tracker_value(
    date: datetime.date,
    tracker_id: int,
    body: TrackerValueUpsert,
    service: TrackerService = Depends(get_tracker_service),
):
    return await service.upsert_tracker_value(date, tracker_id, body.value)
