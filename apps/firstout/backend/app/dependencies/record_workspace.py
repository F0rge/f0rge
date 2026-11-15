from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.record_workspace import RecordWorkspaceService
from app.services.record_workspace_execute import RecordWorkspaceExecuteService


def get_record_workspace_service(db: AsyncSession = Depends(get_db)) -> RecordWorkspaceService:
    return RecordWorkspaceService(db)


def get_record_workspace_execute_service(
    db: AsyncSession = Depends(get_db),
) -> RecordWorkspaceExecuteService:
    return RecordWorkspaceExecuteService(db)
