from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.nia import utc_month_start_naive
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import UserCRUD
from app.exceptions import NiaCapExceededError
from app.models.team_settings import TeamSettings
from app.models.user import User
from app.services.nia_usage import NiaUsageService
from f0rge_core.exceptions import NotFoundError


def effective_nia_cap(user: User, team_settings: TeamSettings) -> int:
    if user.nia_monthly_token_cap is not None:
        return user.nia_monthly_token_cap
    return team_settings.nia_monthly_token_cap


async def check_nia_budget(db: AsyncSession, user_id: uuid.UUID) -> None:
    user_crud = UserCRUD(db)
    user = await user_crud.get_by_id(user_id)
    if user is None:
        raise NotFoundError("User not found")

    team_settings = await TeamSettingsCRUD(db).get_or_create_for_team(user.team_id)
    cap = effective_nia_cap(user, team_settings)
    if cap <= 0:
        raise NiaCapExceededError()

    usage_service = NiaUsageService(db)
    used = await usage_service.sum_total_tokens_for_user_current_utc_month(user_id)
    if used >= cap:
        raise NiaCapExceededError()


class NiaCapsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_crud = UserCRUD(db)
        self.team_settings_crud = TeamSettingsCRUD(db)
        self.usage_service = NiaUsageService(db)

    async def get_my_usage(self, user_id: uuid.UUID) -> dict[str, object]:
        user = await self._get_user(user_id)
        team_settings = await self.team_settings_crud.get_or_create_for_team(user.team_id)
        used = await self.usage_service.sum_total_tokens_for_user_current_utc_month(user_id)
        cap = effective_nia_cap(user, team_settings)
        remaining = max(cap - used, 0)
        period_start = utc_month_start_naive()
        return {
            "used": used,
            "cap": cap,
            "remaining": remaining,
            "period_start": period_start,
        }

    async def list_team_usage(self, admin_user_id: uuid.UUID) -> list[dict[str, object]]:
        admin = await self._get_user(admin_user_id)
        team_settings = await self.team_settings_crud.get_or_create_for_team(admin.team_id)
        users = await self.user_crud.list_all()
        team_users = [user for user in users if user.team_id == admin.team_id]
        rows: list[dict[str, object]] = []
        for user in team_users:
            used = await self.usage_service.sum_total_tokens_for_user_current_utc_month(user.id)
            cap = effective_nia_cap(user, team_settings)
            rows.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "used": used,
                    "cap": cap,
                    "override": user.nia_monthly_token_cap,
                    "remaining": max(cap - used, 0),
                }
            )
        return rows

    async def update_user_cap(
        self,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        cap: Optional[int],
    ) -> dict[str, object]:
        admin = await self._get_user(admin_user_id)
        target = await self.user_crud.get_by_id(target_user_id)
        if target is None or target.team_id != admin.team_id:
            raise NotFoundError("User not found")

        target.nia_monthly_token_cap = cap
        await self.db.flush()

        team_settings = await self.team_settings_crud.get_or_create_for_team(admin.team_id)
        used = await self.usage_service.sum_total_tokens_for_user_current_utc_month(target.id)
        effective = effective_nia_cap(target, team_settings)
        return {
            "user_id": target.id,
            "email": target.email,
            "display_name": target.display_name,
            "used": used,
            "cap": effective,
            "override": target.nia_monthly_token_cap,
            "remaining": max(effective - used, 0),
        }

    async def _get_user(self, user_id: uuid.UUID) -> User:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user
