from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_audit_hub_service, get_current_user_id
from app.schemas.audit import AuditEventItem
from app.schemas.page import Page, PageParams, get_page_params
from app.services.audit_hub import AuditHubService

audit_router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@audit_router.get("/events", response_model=Page[AuditEventItem])
async def list_audit_events(
    params: PageParams = Depends(get_page_params),
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: AuditHubService = Depends(get_audit_hub_service),
) -> Page[AuditEventItem]:
    return await service.list_events(user_id, params)
