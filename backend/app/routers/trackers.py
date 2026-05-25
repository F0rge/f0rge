from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.tracker import (
    OrderRequest,
    TrackerCreate,
    TrackerResponse,
    TrackerUpdate,
    TrackerValueResponse,
    TrackerValueUpsert,
)
from app.services import trackers as trackers_service

router = APIRouter(
    prefix="/api/v1",
    tags=["trackers"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/trackers", response_model=list[TrackerResponse])
async def list_trackers(
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.list_trackers(db, include_archived=include_archived)


@router.post("/trackers", response_model=TrackerResponse, status_code=status.HTTP_201_CREATED)
async def create_tracker(
    body: TrackerCreate,
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.create_tracker(db, body)


@router.patch("/trackers/reorder", response_model=list[TrackerResponse])
async def reorder_trackers(
    body: OrderRequest,
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.reorder_trackers(db, body.order)


@router.patch("/trackers/{tracker_id}", response_model=TrackerResponse)
async def update_tracker(
    tracker_id: int,
    body: TrackerUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.update_tracker(db, tracker_id, body)


@router.get("/entries/{date}/tracker_values", response_model=list[TrackerValueResponse])
async def list_tracker_values(
    date: datetime.date,
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.list_tracker_values(db, date)


@router.put(
    "/entries/{date}/tracker_values/{tracker_id}",
    response_model=TrackerValueResponse,
)
async def upsert_tracker_value(
    date: datetime.date,
    tracker_id: int,
    body: TrackerValueUpsert,
    db: AsyncSession = Depends(get_db),
):
    return await trackers_service.upsert_tracker_value(db, date, tracker_id, body.value)
