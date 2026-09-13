from __future__ import annotations

import datetime
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.books_period import BooksPeriodCRUD
from app.models.books_period import BooksPeriod, BooksPeriodStatus
from app.schemas.books_period import (
    BooksPeriodCreate,
    BooksPeriodReopen,
    BooksPeriodResponse,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


async def assert_date_postable(db: AsyncSession, target_date: datetime.date) -> None:
    locked = await BooksPeriodCRUD(db).find_locked_covering(target_date)
    if locked is not None:
        raise ConflictError("Books period is locked for this date")


class BooksPeriodService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BooksPeriodCRUD(db)

    async def list(self) -> list[BooksPeriodResponse]:
        return [self._to_response(period) for period in await self.crud.list_all()]

    async def create(self, data: BooksPeriodCreate) -> BooksPeriodResponse:
        self._validate_range(data.period_from, data.period_to)
        existing = await self.crud.find_overlapping(data.period_from, data.period_to)
        if existing is not None:
            raise ConflictError("Books period overlaps an existing period")

        period = BooksPeriod(
            period_from=data.period_from,
            period_to=data.period_to,
            status=BooksPeriodStatus.OPEN,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(period)
        except IntegrityError as exc:
            raise ConflictError("Books period overlaps an existing period") from exc
        return self._to_response(period)

    async def get(self, period_id: uuid.UUID) -> BooksPeriodResponse:
        return self._to_response(await self._get_or_404(period_id))

    async def lock(self, period_id: uuid.UUID, user_id: uuid.UUID) -> BooksPeriodResponse:
        period = await self._get_or_404(period_id)
        if period.status == BooksPeriodStatus.LOCKED:
            raise ConflictError("Books period is already locked")

        locked_at = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            period.status = BooksPeriodStatus.LOCKED
            period.locked_at = locked_at
            period.locked_by_user_id = user_id
        return self._to_response(period)

    async def reopen(
        self, period_id: uuid.UUID, user_id: uuid.UUID, data: BooksPeriodReopen
    ) -> BooksPeriodResponse:
        reason = data.reason.strip()
        if not reason:
            raise ValidationError("reason is required")
        period = await self._get_or_404(period_id)
        if period.status != BooksPeriodStatus.LOCKED:
            raise ConflictError("Books period is not locked")

        async with unit_of_work(self.db):
            period.status = BooksPeriodStatus.OPEN
            period.reopen_reason = reason
            period.locked_at = None
            period.locked_by_user_id = None
        return self._to_response(period)

    async def _get_or_404(self, period_id: uuid.UUID) -> BooksPeriod:
        period = await self.crud.get_by_id(period_id)
        if period is None:
            raise NotFoundError("Books period not found")
        return period

    @staticmethod
    def _validate_range(period_from: datetime.date, period_to: datetime.date) -> None:
        if period_from > period_to:
            raise ValidationError("period_from must be on or before period_to")

    @staticmethod
    def _to_response(period: BooksPeriod) -> BooksPeriodResponse:
        return BooksPeriodResponse(
            id=period.id,
            period_from=period.period_from,
            period_to=period.period_to,
            status=period.status,
            locked_at=period.locked_at,
            locked_by_user_id=period.locked_by_user_id,
            reopen_reason=period.reopen_reason,
            created_at=period.created_at,
            updated_at=period.updated_at,
        )
