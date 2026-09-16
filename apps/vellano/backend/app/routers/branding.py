from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.database import get_db
from app.schemas.platform_signup import BrandingResponse
from app.tenancy.context import tenant_ctx

branding_router = APIRouter(prefix="/api/v1", tags=["branding"])


@branding_router.get("/branding", response_model=BrandingResponse)
async def get_branding(db: AsyncSession = Depends(get_db)) -> BrandingResponse:
    ctx = tenant_ctx.get()
    slug = ctx.slug if ctx is not None else ""
    team = await TeamCRUD(db).get_first()
    display = ""
    if team is not None:
        row = await TeamSettingsCRUD(db).get_by_team_id(team.id)
        if row is not None:
            display = (row.trading_name or row.legal_name or "").strip()
        if not display:
            display = team.name
    if not display:
        display = slug or "Workspace"
    return BrandingResponse(display_name=display, slug=slug)
