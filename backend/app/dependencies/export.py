from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.export import ExportService


def get_export_service(db: AsyncSession = Depends(get_db)) -> ExportService:
    return ExportService(db)
