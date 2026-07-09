from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.entries import get_entry_service
from app.middleware.auth import get_current_session
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.services.entries import EntryService

router = APIRouter(
    prefix="/api/v1/entries",
    tags=["entries"],
    dependencies=[Depends(get_current_session)],
)


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(body: EntryCreate, service: EntryService = Depends(get_entry_service)):
    return await service.create_entry(body)


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    service: EntryService = Depends(get_entry_service),
):
    return await service.list_entries(month)


@router.get("/{date}", response_model=EntryResponse)
async def get_entry(date: datetime.date, service: EntryService = Depends(get_entry_service)):
    return await service.get_entry(date)


@router.put("/{date}", response_model=EntryResponse)
async def update_entry(
    date: datetime.date,
    body: EntryUpdate,
    service: EntryService = Depends(get_entry_service),
):
    return await service.update_entry(date, body)


@router.delete("/{date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(date: datetime.date, service: EntryService = Depends(get_entry_service)):
    await service.delete_entry(date)
