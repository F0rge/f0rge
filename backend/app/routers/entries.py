from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_session
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.services import entries as entries_service

router = APIRouter(
    prefix="/api/v1/entries",
    tags=["entries"],
    dependencies=[Depends(get_current_session)],
)


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(body: EntryCreate, db: AsyncSession = Depends(get_db)):
    return await entries_service.create_entry(db, body)


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    return await entries_service.list_entries(db, month)


@router.get("/{date}", response_model=EntryResponse)
async def get_entry(date: datetime.date, db: AsyncSession = Depends(get_db)):
    return await entries_service.get_entry(db, date)


@router.put("/{date}", response_model=EntryResponse)
async def update_entry(date: datetime.date, body: EntryUpdate, db: AsyncSession = Depends(get_db)):
    return await entries_service.update_entry(db, date, body)


@router.delete("/{date}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(date: datetime.date, db: AsyncSession = Depends(get_db)):
    await entries_service.delete_entry(db, date)
