from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.entries import EntryService
from app.services.entry_orchestrator import EntryOrchestrator


def get_entry_service(db: AsyncSession = Depends(get_db)) -> EntryService:
    return EntryService(db)


def get_entry_orchestrator(db: AsyncSession = Depends(get_db)) -> EntryOrchestrator:
    return EntryOrchestrator(db)
