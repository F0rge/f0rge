from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_settings import (
    DEFAULT_HOME_CURRENCY,
    DEFAULT_NIA_MONTHLY_TOKEN_CAP,
    DEFAULT_VAT_RATE,
    TeamSettings,
)
from app.services.document_numbering import DocumentNumberingService
from f0rge_db.crud import BaseCRUD, unit_of_work


class TeamSettingsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_team_id(self, team_id: uuid.UUID) -> Optional[TeamSettings]:
        result = await self.db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
        return result.scalar_one_or_none()

    async def get_or_create_for_team(self, team_id: uuid.UUID) -> TeamSettings:
        existing = await self.get_by_team_id(team_id)
        numbering = DocumentNumberingService(self.db)
        if existing is not None:
            await numbering.ensure_all_for_team(team_id)
            return existing
        settings = TeamSettings(
            team_id=team_id,
            vat_rate=DEFAULT_VAT_RATE,
            home_currency=DEFAULT_HOME_CURRENCY,
            always_prefer_warehouse=True,
            pick_priority=[],
            nia_monthly_token_cap=DEFAULT_NIA_MONTHLY_TOKEN_CAP,
        )
        async with unit_of_work(self.db):
            await self.add_and_flush(settings)
        await numbering.ensure_all_for_team(team_id)
        return settings
