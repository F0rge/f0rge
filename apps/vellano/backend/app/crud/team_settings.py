from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_settings import DEFAULT_HOME_CURRENCY, DEFAULT_VAT_RATE, TeamSettings
from f0rge_db.crud import BaseCRUD


class TeamSettingsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_team_id(self, team_id: uuid.UUID) -> TeamSettings | None:
        result = await self.db.execute(
            select(TeamSettings).where(TeamSettings.team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_for_team(self, team_id: uuid.UUID) -> TeamSettings:
        existing = await self.get_by_team_id(team_id)
        if existing is not None:
            return existing
        settings = TeamSettings(
            team_id=team_id,
            vat_rate=DEFAULT_VAT_RATE,
            home_currency=DEFAULT_HOME_CURRENCY,
        )
        await self.add_and_flush(settings)
        return settings
