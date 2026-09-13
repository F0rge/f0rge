from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.document_sequence import DOCUMENT_TYPE_DEFAULTS, DocumentSequenceCRUD
from app.crud.location import LocationCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import UserCRUD
from app.models.location import LocationType
from app.models.team_settings import DEFAULT_HOME_CURRENCY, DEFAULT_VAT_RATE
from app.schemas.settings import (
    DocumentSequenceResponse,
    SettingsResponse,
    SettingsUpdate,
)
from app.services.document_numbering import DocumentNumberingService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class SettingsService:
    DEFAULT_WARNING = (
        "Vellano V1 defaults are VAT 15% and home currency ZAR. "
        "Changing these does not file with SARS."
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TeamSettingsCRUD(db)
        self.user_crud = UserCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sequence_crud = DocumentSequenceCRUD(db)
        self.numbering = DocumentNumberingService(db)

    async def get_for_user(self, user_id: uuid.UUID) -> SettingsResponse:
        user = await self._get_user(user_id)
        settings = await self.crud.get_or_create_for_team(user.team_id)
        return await self._to_response(settings)

    async def update(self, user_id: uuid.UUID, data: SettingsUpdate) -> SettingsResponse:
        user = await self._get_user(user_id)
        settings = await self.crud.get_or_create_for_team(user.team_id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            raise ValidationError("No settings fields to update")

        async with unit_of_work(self.db):
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
            if data.legal_name is not None:
                settings.legal_name = data.legal_name
            if "trading_name" in payload:
                settings.trading_name = data.trading_name
            if data.address is not None:
                settings.address = data.address
            if data.vat_number is not None:
                settings.vat_number = data.vat_number
            if "cipc_number" in payload:
                settings.cipc_number = data.cipc_number
            if "bank_name" in payload:
                settings.bank_name = data.bank_name
            if "bank_account" in payload:
                settings.bank_account = data.bank_account
            if "bank_branch_code" in payload:
                settings.bank_branch_code = data.bank_branch_code
            if data.payment_terms_days is not None:
                settings.payment_terms_days = data.payment_terms_days
            if "default_receive_location_id" in payload:
                settings.default_receive_location_id = await self._validate_default_location(
                    data.default_receive_location_id,
                    LocationType.WAREHOUSE,
                    "receive",
                )
            if "default_till_location_id" in payload:
                settings.default_till_location_id = await self._validate_default_location(
                    data.default_till_location_id,
                    LocationType.SHOWROOM,
                    "till",
                )
            if data.document_sequences is not None:
                await self._apply_sequence_updates(user.team_id, data.document_sequences)

        return await self._to_response(settings, include_warning=True)

    async def _validate_default_location(
        self,
        location_id: Optional[uuid.UUID],
        expected_type: LocationType,
        label: str,
    ) -> Optional[uuid.UUID]:
        if location_id is None:
            return None
        location = await self.location_crud.get_by_id(location_id)
        if location is None or location.is_archived:
            raise ValidationError(f"Unknown or archived location for {label} default")
        if location.type != expected_type:
            raise ValidationError(
                f"Default {label} location must be a {expected_type.value} location"
            )
        return location.id

    async def _apply_sequence_updates(self, team_id: uuid.UUID, updates) -> None:
        await self.numbering.ensure_all_for_team(team_id)
        for item in updates:
            if item.doc_type not in DOCUMENT_TYPE_DEFAULTS:
                raise ValidationError(f"Unknown document sequence type: {item.doc_type}")
            row = await self.sequence_crud.get_by_team_and_type(team_id, item.doc_type)
            if row is None:
                raise ValidationError(f"Document sequence not found: {item.doc_type}")
            if item.prefix is not None:
                row.prefix = DocumentNumberingService.normalize_prefix(item.prefix)
            if item.padding is not None:
                row.padding = item.padding

    async def _get_user(self, user_id: uuid.UUID):
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def _to_response(
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

        sequences = await self.sequence_crud.list_for_team(settings.team_id)
        sequence_rows = [
            DocumentSequenceResponse(
                doc_type=row.doc_type,
                prefix=row.prefix,
                padding=row.padding,
                next_value=int(row.next_value),
            )
            for row in sequences
        ]

        return SettingsResponse(
            vat_rate=vat_rate,
            vat_percent=(vat_rate * Decimal("100")).quantize(Decimal("0.01")),
            home_currency=home_currency,
            defaults_locked=defaults_locked,
            warning=warning,
            always_prefer_warehouse=bool(settings.always_prefer_warehouse),
            pick_priority=parse_pick_priority(settings.pick_priority),
            nia_monthly_token_cap=int(settings.nia_monthly_token_cap),
            legal_name=settings.legal_name,
            trading_name=settings.trading_name,
            address=settings.address,
            vat_number=settings.vat_number,
            cipc_number=settings.cipc_number,
            bank_name=settings.bank_name,
            bank_account=settings.bank_account,
            bank_branch_code=settings.bank_branch_code,
            payment_terms_days=int(settings.payment_terms_days),
            default_receive_location_id=settings.default_receive_location_id,
            default_till_location_id=settings.default_till_location_id,
            document_sequences=sequence_rows,
        )


def parse_pick_priority(raw: object) -> list[uuid.UUID]:
    if not raw:
        return []
    return [uuid.UUID(str(item)) for item in raw]
