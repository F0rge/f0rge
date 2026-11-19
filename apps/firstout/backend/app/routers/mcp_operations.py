from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import require_directory_tenant
from app.database import get_db
from app.dependencies.tenant_signup import get_clerk_api
from app.middleware.auth import get_current_user_id
from app.services.clerk_api import ClerkAPI
from app.services.mcp_operations import confirm_staff_review, staff_review

router = APIRouter(prefix="/api/v1/mcp-operations", tags=["mcp-operations"])
Staff = Annotated[uuid.UUID, Depends(get_current_user_id)]
Database = Annotated[AsyncSession, Depends(get_db)]
Provider = Annotated[ClerkAPI, Depends(get_clerk_api)]


@router.get("/{operation_id}")
async def review_operation(
    operation_id: uuid.UUID,
    response: Response,
    user_id: Staff,
    db: Database,
    provider: Provider,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await staff_review(db, require_directory_tenant(), user_id, operation_id, provider)


@router.post("/{operation_id}/confirm")
async def confirm_operation(
    operation_id: uuid.UUID,
    response: Response,
    user_id: Staff,
    db: Database,
    provider: Provider,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await confirm_staff_review(
        db, require_directory_tenant(), user_id, operation_id, provider
    )
