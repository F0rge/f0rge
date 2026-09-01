from __future__ import annotations

import calendar
import datetime
import uuid
from typing import Any, Optional

from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.vat201_period import Vat201PeriodCRUD
from app.models.vat201_period import (
    Vat201Period,
    Vat201PeriodEvent,
    Vat201PeriodEventAction,
    Vat201PeriodStatus,
)
from app.schemas.bank_import import Vat201Draft
from app.schemas.vat201_period import (
    Vat201PeriodCreate,
    Vat201PeriodDetailResponse,
    Vat201PeriodReopen,
    Vat201PeriodResponse,
)
from app.services.reports import ReportsService
from app.services.vat201_export import build_vat201_csv, build_vat201_pdf
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def expected_bimonthly_to(period_from: datetime.date) -> datetime.date:
    month = period_from.month + 1
    year = period_from.year
    if month > 12:
        month -= 12
        year += 1
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


class Vat201PeriodService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = Vat201PeriodCRUD(db)
        self.reports = ReportsService(db)

    async def list(self) -> list[Vat201PeriodResponse]:
        return [self._to_list_response(period) for period in await self.crud.list_all()]

    async def create(self, data: Vat201PeriodCreate) -> Vat201PeriodDetailResponse:
        self._validate_range(data.period_from, data.period_to)
        existing = await self.crud.find_overlapping(data.period_from, data.period_to)
        if existing is not None:
            raise ConflictError("VAT201 period overlaps an existing period")

        period = Vat201Period(
            period_from=data.period_from,
            period_to=data.period_to,
            status=Vat201PeriodStatus.DRAFT,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(period)
        except IntegrityError as exc:
            raise ConflictError("VAT201 period overlaps an existing period") from exc
        return await self.get(period.id)

    async def get(self, period_id: uuid.UUID) -> Vat201PeriodDetailResponse:
        period = await self._get_or_404(period_id)
        return self._to_detail_response(period, await self._draft_for(period))

    async def lock(self, period_id: uuid.UUID, user_id: uuid.UUID) -> Vat201PeriodDetailResponse:
        period = await self._get_or_404(period_id)
        if period.status == Vat201PeriodStatus.LOCKED:
            raise ConflictError("VAT201 period is already locked")

        draft = await self.reports.vat201_draft(period.period_from, period.period_to)
        snapshot = draft.model_dump(mode="json")
        locked_at = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            period.status = Vat201PeriodStatus.LOCKED
            period.snapshot_json = snapshot
            period.locked_at = locked_at
            period.locked_by_user_id = user_id
            await self.crud.add_event(
                Vat201PeriodEvent(
                    period_id=period.id,
                    action=Vat201PeriodEventAction.LOCK,
                    snapshot_json=snapshot,
                    actor_user_id=user_id,
                )
            )
        return self._to_detail_response(period, draft)

    async def reopen(
        self, period_id: uuid.UUID, user_id: uuid.UUID, data: Vat201PeriodReopen
    ) -> Vat201PeriodDetailResponse:
        reason = data.reason.strip()
        if not reason:
            raise ValidationError("reason is required")
        period = await self._get_or_404(period_id)
        if period.status != Vat201PeriodStatus.LOCKED:
            raise ConflictError("VAT201 period is not locked")

        async with unit_of_work(self.db):
            period.status = Vat201PeriodStatus.DRAFT
            period.reopen_reason = reason
            await self.crud.add_event(
                Vat201PeriodEvent(
                    period_id=period.id,
                    action=Vat201PeriodEventAction.REOPEN,
                    snapshot_json=period.snapshot_json,
                    actor_user_id=user_id,
                    reason=reason,
                )
            )
        return await self.get(period.id)

    async def serve_csv(self, period_id: uuid.UUID) -> Response:
        period = await self._get_or_404(period_id)
        draft = await self._draft_for(period)
        filename = f"vat201-{period.period_from.isoformat()}-to-{period.period_to.isoformat()}.csv"
        return Response(
            content=build_vat201_csv(draft),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def serve_pdf(self, period_id: uuid.UUID) -> Response:
        period = await self._get_or_404(period_id)
        draft = await self._draft_for(period)
        filename = f"vat201-{period.period_from.isoformat()}-to-{period.period_to.isoformat()}.pdf"
        return Response(
            content=build_vat201_pdf(draft),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def _get_or_404(self, period_id: uuid.UUID) -> Vat201Period:
        period = await self.crud.get_by_id(period_id)
        if period is None:
            raise NotFoundError("VAT201 period not found")
        return period

    async def _draft_for(self, period: Vat201Period) -> Vat201Draft:
        if period.status == Vat201PeriodStatus.LOCKED:
            return self._draft_from_snapshot(period.snapshot_json)
        return await self.reports.vat201_draft(period.period_from, period.period_to)

    def _to_list_response(self, period: Vat201Period) -> Vat201PeriodResponse:
        return Vat201PeriodResponse(
            id=period.id,
            period_from=period.period_from,
            period_to=period.period_to,
            status=self._exposed_status(period),
            locked_at=period.locked_at,
            locked_by_user_id=period.locked_by_user_id,
            reopen_reason=period.reopen_reason,
            created_at=period.created_at,
            updated_at=period.updated_at,
        )

    def _to_detail_response(
        self, period: Vat201Period, draft: Vat201Draft
    ) -> Vat201PeriodDetailResponse:
        return Vat201PeriodDetailResponse(
            id=period.id,
            period_from=period.period_from,
            period_to=period.period_to,
            status=self._exposed_status(period),
            locked_at=period.locked_at,
            locked_by_user_id=period.locked_by_user_id,
            reopen_reason=period.reopen_reason,
            created_at=period.created_at,
            updated_at=period.updated_at,
            draft=draft,
        )

    @staticmethod
    def _exposed_status(period: Vat201Period) -> Vat201PeriodStatus:
        if period.status == Vat201PeriodStatus.DRAFT and datetime.date.today() > period.period_to:
            return Vat201PeriodStatus.DUE
        return period.status

    @staticmethod
    def _validate_range(period_from: datetime.date, period_to: datetime.date) -> None:
        if period_from.day != 1:
            raise ValidationError("VAT201 period must start on the first day of a month")
        expected = expected_bimonthly_to(period_from)
        if period_to != expected:
            raise ValidationError("VAT201 period must cover exactly two calendar months")

    @staticmethod
    def _draft_from_snapshot(snapshot: Optional[dict[str, Any]]) -> Vat201Draft:
        if snapshot is None:
            raise ConflictError("Locked VAT201 period is missing a snapshot")
        return Vat201Draft.model_validate(snapshot)
