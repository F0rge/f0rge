from __future__ import annotations

import calendar
import datetime
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.repeating_invoice import RepeatingInvoiceCRUD
from app.models.repeating_invoice import RepeatingInvoice, RepeatingInvoiceLine
from app.schemas.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.repeating_invoice import (
    RepeatingInvoiceCreate,
    RepeatingInvoiceLineResponse,
    RepeatingInvoiceResponse,
    RepeatingInvoiceRunResponse,
    RepeatingInvoiceUpdate,
)
from app.services.contacts import ContactService
from app.services.invoices import InvoiceService
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def advance_month(current: datetime.date, day_of_month: int) -> datetime.date:
    month = current.month + 1
    year = current.year
    if month > 12:
        month -= 12
        year += 1
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day_of_month, last))


class RepeatingInvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = RepeatingInvoiceCRUD(db)
        self.contact_service = ContactService(db)
        self.invoice_service = InvoiceService(db)

    async def list(self) -> list[RepeatingInvoiceResponse]:
        return [self._to_response(row) for row in await self.crud.list_all()]

    async def get(self, schedule_id: uuid.UUID) -> RepeatingInvoiceResponse:
        return self._to_response(await self._get_or_404(schedule_id))

    async def create(
        self, data: RepeatingInvoiceCreate, user_id: uuid.UUID
    ) -> RepeatingInvoiceResponse:
        await self.contact_service.get_customer(data.customer_id)
        schedule = RepeatingInvoice(
            customer_id=data.customer_id,
            name=data.name,
            day_of_month=data.day_of_month,
            next_date=data.next_date,
            created_by=user_id,
            lines=[
                RepeatingInvoiceLine(
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    sort_order=index,
                )
                for index, line in enumerate(data.lines)
            ],
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(schedule)
        return self._to_response(await self._get_or_404(schedule.id))

    async def update(
        self, schedule_id: uuid.UUID, data: RepeatingInvoiceUpdate
    ) -> RepeatingInvoiceResponse:
        schedule = await self._get_or_404(schedule_id)
        fields_set = data.model_fields_set
        if "name" in fields_set:
            schedule.name = data.name
        if data.day_of_month is not None:
            schedule.day_of_month = data.day_of_month
        if data.next_date is not None:
            schedule.next_date = data.next_date
        if data.is_active is not None:
            schedule.is_active = data.is_active
        await self.crud.commit_refresh(schedule)
        return self._to_response(await self._get_or_404(schedule.id))

    async def run(
        self, schedule_id: uuid.UUID, user_id: Optional[uuid.UUID] = None
    ) -> RepeatingInvoiceRunResponse:
        schedule = await self._get_or_404(schedule_id)
        if not schedule.is_active:
            raise ValidationError("Repeating invoice is not active")
        if not schedule.lines:
            raise ValidationError("Repeating invoice has no lines")

        invoice = await self.invoice_service.create(
            InvoiceCreate(
                customer_id=schedule.customer_id,
                issue_date=min(schedule.next_date, datetime.date.today()),
                lines=[
                    InvoiceLineCreate(
                        description=line.description,
                        qty=line.qty,
                        unit_ex_vat=line.unit_ex_vat,
                    )
                    for line in schedule.lines
                ],
            ),
            user_id,
        )
        schedule.next_date = advance_month(schedule.next_date, schedule.day_of_month)
        await self.crud.commit_refresh(schedule)
        return RepeatingInvoiceRunResponse(
            schedule=self._to_response(await self._get_or_404(schedule.id)),
            invoice=invoice,
        )

    async def _get_or_404(self, schedule_id: uuid.UUID) -> RepeatingInvoice:
        schedule = await self.crud.get_by_id(schedule_id)
        if schedule is None:
            raise NotFoundError("Repeating invoice not found")
        return schedule

    @staticmethod
    def _to_response(schedule: RepeatingInvoice) -> RepeatingInvoiceResponse:
        return RepeatingInvoiceResponse(
            id=schedule.id,
            customer_id=schedule.customer_id,
            name=schedule.name,
            day_of_month=schedule.day_of_month,
            next_date=schedule.next_date,
            is_active=schedule.is_active,
            created_by=schedule.created_by,
            lines=[
                RepeatingInvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    sort_order=line.sort_order,
                )
                for line in schedule.lines
            ],
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
