from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import UserCRUD
from app.models.team_settings import DEFAULT_HOME_CURRENCY, DEFAULT_VAT_RATE
from app.schemas.settings import SettingsResponse, SettingsUpdate
from f0rge_core.exceptions import NotFoundError, ValidationError


class SettingsService:
    DEFAULT_WARNING = (
        "Vellano V1 defaults are VAT 15% and home currency ZAR. "
        "Changing these does not file with SARS."
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TeamSettingsCRUD(db)
        self.user_crud = UserCRUD(db)

    async def get_for_user(self, user_id: uuid.UUID) -> SettingsResponse:
        user = await self._get_user(user_id)
        settings = await self.crud.get_or_create_for_team(user.team_id)
        return self._to_response(settings)

    async def update(self, user_id: uuid.UUID, data: SettingsUpdate) -> SettingsResponse:
        user = await self._get_user(user_id)
        settings = await self.crud.get_or_create_for_team(user.team_id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            raise ValidationError("No settings fields to update")

        if data.vat_rate is not None:
            if data.vat_rate <= 0 or data.vat_rate > 1:
                raise ValidationError("vat_rate must be between 0 and 1")
            settings.vat_rate = data.vat_rate
        if data.home_currency is not None:
            settings.home_currency = data.home_currency.upper()
        if data.always_prefer_warehouse is not None:
            settings.always_prefer_warehouse = data.always_prefer_warehouse
        if data.pick_priority is not None:
            settings.pick_priority = [str(item) for item in data.pick_priority]
        if data.nia_monthly_token_cap is not None:
            settings.nia_monthly_token_cap = data.nia_monthly_token_cap
        await self.db.flush()
        return self._to_response(settings, include_warning=True)

    async def _get_user(self, user_id: uuid.UUID):
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def _to_response(
        self,
        settings,
        *,
        include_warning: bool = False,
    ) -> SettingsResponse:
        vat_rate = settings.vat_rate
        home_currency = settings.home_currency
        defaults_locked = vat_rate == DEFAULT_VAT_RATE and home_currency == DEFAULT_HOME_CURRENCY
        warning = None
        if not defaults_locked:
            warning = self.DEFAULT_WARNING

        return SettingsResponse(
            vat_rate=vat_rate,
            vat_percent=(vat_rate * Decimal("100")).quantize(Decimal("0.01")),
            home_currency=home_currency,
            defaults_locked=defaults_locked,
            warning=warning,
            always_prefer_warehouse=bool(settings.always_prefer_warehouse),
            pick_priority=parse_pick_priority(settings.pick_priority),
            nia_monthly_token_cap=int(settings.nia_monthly_token_cap),
        )


def parse_pick_priority(raw: object) -> list[uuid.UUID]:
    if not raw:
        return []
    return [uuid.UUID(str(item)) for item in raw]
