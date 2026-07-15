from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.entries import get_entry_orchestrator, get_entry_service
from app.middleware.auth import get_current_session
from app.schemas.entry import EntryCreate, EntryResponse, EntryStatsResponse, EntryUpdate
from app.services.entries import EntryService
from app.services.entry_orchestrator import EntryOrchestrator

router = APIRouter(
    prefix="/api/v1/entries",
    tags=["entries"],
    dependencies=[Depends(get_current_session)],
)


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    body: EntryCreate,
    orchestrator: EntryOrchestrator = Depends(get_entry_orchestrator),
):
    return await orchestrator.create_entry(body)


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    service: EntryService = Depends(get_entry_service),
):
    return await service.list_entries(month)


# Must stay above GET /{date} — FastAPI matches in declaration order, and
# /{date} would otherwise 422 trying to parse "stats" as a date.
@router.get("/stats", response_model=EntryStatsResponse)
async def entry_stats(service: EntryService = Depends(get_entry_service)):
    return await service.stats()


@router.get("/{date}", response_model=EntryResponse)
async def get_entry(date: datetime.date, service: EntryService = Depends(get_entry_service)):
    return await service.get_entry(date)


@router.put("/{date}", response_model=EntryResponse)
async def update_entry(
    date: datetime.date,
    body: EntryUpdate,
    orchestrator: EntryOrchestrator = Depends(get_entry_orchestrator),
):
    return await orchestrator.update_entry(date, body)


@router.delete("/{date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(date: datetime.date, service: EntryService = Depends(get_entry_service)):
    await service.delete_entry(date)
