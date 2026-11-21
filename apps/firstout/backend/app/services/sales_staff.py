"""Sales staff (who made each sale) and the monthly commission they earn.

Commission base: invoice line ex VAT after discount, counted in the invoice's issue month.
Lines snapshotted as excluded (delivery, installation, ...) earn nothing. A credit note
deducts the commissionable part of what it credits in its own issue month, from the
original invoice's colleague. Imported (``is_archive``) invoices never count.
"""

from __future__ import annotations

import calendar
import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import exists, false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.quote import Quote
from app.models.sales_staff import SalesStaff
from app.models.stock_return import StockReturn, StockReturnLine
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.sales_staff import (
    CommissionDocument,
    CommissionReport,
    CommissionRow,
    SalesStaffCreate,
    SalesStaffResponse,
    SalesStaffUpdate,
)
from app.services.vat import CENT
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

ZERO = Decimal("0.00")


def month_bounds(month: str) -> tuple[datetime.date, datetime.date]:
    try:
        start = datetime.datetime.strptime(month, "%Y-%m").date()
    except ValueError as exc:
        raise ValidationError("month must be YYYY-MM") from exc
    return start, start.replace(day=calendar.monthrange(start.year, start.month)[1])


class SalesStaffService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, *, active: Optional[bool] = None) -> list[SalesStaff]:
        stmt = select(SalesStaff).order_by(func.lower(SalesStaff.name), SalesStaff.id)
        if active is not None:
            stmt = stmt.where(SalesStaff.is_active.is_(active))
        return list((await self.db.scalars(stmt)).all())

    async def _get(self, staff_id: uuid.UUID, *, for_update: bool = False) -> SalesStaff:
        stmt = select(SalesStaff).where(SalesStaff.id == staff_id)
        if for_update:
            stmt = stmt.with_for_update()
        staff = (await self.db.scalars(stmt)).one_or_none()
        if staff is None:
            raise NotFoundError("Sales colleague not found")
        return staff

    async def create(self, data: SalesStaffCreate) -> SalesStaffResponse:
        async with unit_of_work(self.db):
            staff = SalesStaff(**data.model_dump())
            self.db.add(staff)
            await self.db.flush()
            await self.db.refresh(staff)
        return SalesStaffResponse.model_validate(staff)

    async def update(self, staff_id: uuid.UUID, data: SalesStaffUpdate) -> SalesStaffResponse:
        async with unit_of_work(self.db):
            staff = await self._get(staff_id, for_update=True)
            for field in data.model_fields_set:
                value = getattr(data, field)
                if value is None and field != "short_name":
                    raise ValidationError(f"{field} must not be null")
                setattr(staff, field, value)
            await self.db.flush()
            await self.db.refresh(staff)
        return SalesStaffResponse.model_validate(staff)

    async def delete(self, staff_id: uuid.UUID) -> None:
        """Only a colleague no invoice or quote names; otherwise deactivate them."""
        async with unit_of_work(self.db):
            staff = await self._get(staff_id, for_update=True)
            referenced = await self.db.scalar(
                select(
                    exists().where(TaxInvoice.sales_staff_id == staff_id)
                    | exists().where(Quote.sales_staff_id == staff_id)
                )
            )
            if referenced:
                raise ConflictError(
                    "This colleague is named on invoices or quotes. Deactivate them instead."
                )
            await self.db.delete(staff)

    async def assert_assignable(self, staff_id: uuid.UUID) -> None:
        """Any colleague of this organisation, active or not (past invoices)."""
        await self._get(staff_id)

    async def check_sale_colleague(self, staff_id: Optional[uuid.UUID]) -> None:
        """A sale names an active colleague whenever the business has one."""
        if staff_id is not None:
            staff = await self.db.scalar(select(SalesStaff).where(SalesStaff.id == staff_id))
            if staff is None or not staff.is_active:
                raise ValidationError("Choose an active sales colleague")
            return
        if await self.db.scalar(select(exists().where(SalesStaff.is_active.is_(True)))):
            raise ValidationError("Choose the sales colleague who made this sale")

    async def commission_report(self, month: str) -> CommissionReport:
        start, end = month_bounds(month)
        commissionable = func.coalesce(
            func.sum(InvoiceLine.ex_vat).filter(InvoiceLine.exclude_from_commission.is_(False)),
            0,
        )
        excluded = func.coalesce(
            func.sum(InvoiceLine.ex_vat).filter(InvoiceLine.exclude_from_commission.is_(True)),
            0,
        )
        invoices = (
            await self.db.execute(
                select(
                    TaxInvoice.id,
                    TaxInvoice.invoice_number,
                    TaxInvoice.issue_date,
                    TaxInvoice.sales_staff_id,
                    Customer.name,
                    commissionable,
                    excluded,
                )
                .join(Customer, Customer.id == TaxInvoice.customer_id)
                .outerjoin(InvoiceLine, InvoiceLine.invoice_id == TaxInvoice.id)
                .where(
                    TaxInvoice.issue_date.between(start, end),
                    TaxInvoice.is_archive.is_(false()),
                )
                .group_by(TaxInvoice.id, Customer.name)
                .order_by(TaxInvoice.issue_date, TaxInvoice.invoice_number)
            )
        ).all()

        docs: dict[Optional[uuid.UUID], list[CommissionDocument]] = {}
        for row in invoices:
            docs.setdefault(row.sales_staff_id, []).append(
                CommissionDocument(
                    kind="invoice",
                    id=row.id,
                    number=row.invoice_number,
                    invoice_id=row.id,
                    invoice_number=row.invoice_number,
                    issue_date=row.issue_date,
                    customer_name=row.name,
                    commissionable_ex_vat=Decimal(row[5]).quantize(CENT),
                    excluded_ex_vat=Decimal(row[6]).quantize(CENT),
                )
            )
        for doc, staff_id in await self._credit_documents(start, end):
            docs.setdefault(staff_id, []).append(doc)

        staff_by_id = {staff.id: staff for staff in await self.list()}
        rows = [
            _row(
                staff.id,
                staff.name,
                staff.short_name,
                staff.is_active,
                staff.commission_rate,
                docs.get(staff.id, []),
            )
            for staff in staff_by_id.values()
            if staff.is_active or staff.id in docs
        ]
        unattributed = _row(None, "Unattributed", None, True, ZERO, docs.get(None, []))
        everyone = [*rows, unattributed]
        return CommissionReport(
            month=start.strftime("%Y-%m"),
            from_date=start,
            to_date=end,
            rows=rows,
            unattributed=unattributed,
            invoice_count=sum(row.invoice_count for row in everyone),
            commissionable_ex_vat=sum((row.commissionable_ex_vat for row in everyone), ZERO),
            excluded_ex_vat=sum((row.excluded_ex_vat for row in everyone), ZERO),
            credit_deductions=sum((row.credit_deductions for row in everyone), ZERO),
            net_commissionable=sum((row.net_commissionable for row in everyone), ZERO),
            commission=sum((row.commission for row in rows), ZERO),
        )

    async def _credit_documents(
        self, start: datetime.date, end: datetime.date
    ) -> list[tuple[CommissionDocument, Optional[uuid.UUID]]]:
        notes = (
            await self.db.execute(
                select(CreditNote, TaxInvoice, Customer.name)
                .join(TaxInvoice, TaxInvoice.id == CreditNote.invoice_id)
                .join(Customer, Customer.id == TaxInvoice.customer_id)
                .where(
                    CreditNote.issue_date.between(start, end),
                    TaxInvoice.is_archive.is_(false()),
                )
                .order_by(CreditNote.issue_date, CreditNote.credit_note_number)
            )
        ).all()
        if not notes:
            return []
        # A return's credit note credits only the returned quantities; any other credit
        # note credits the whole invoice.
        returned: dict[uuid.UUID, list[tuple[InvoiceLine, int]]] = {}
        for credit_note_id, line, qty in (
            await self.db.execute(
                select(StockReturn.credit_note_id, InvoiceLine, StockReturnLine.qty)
                .join(StockReturnLine, StockReturnLine.return_id == StockReturn.id)
                .join(InvoiceLine, InvoiceLine.id == StockReturnLine.invoice_line_id)
                .where(StockReturn.credit_note_id.in_([note.id for note, _, _ in notes]))
            )
        ).all():
            returned.setdefault(credit_note_id, []).append((line, qty))
        whole = {
            invoice_id: []
            for invoice_id in {invoice.id for note, invoice, _ in notes if note.id not in returned}
        }
        if whole:
            for line in await self.db.scalars(
                select(InvoiceLine).where(InvoiceLine.invoice_id.in_(list(whole)))
            ):
                whole[line.invoice_id].append((line, line.qty))

        out = []
        for note, invoice, customer_name in notes:
            credited = returned.get(note.id) or whole.get(invoice.id, [])
            split = {False: ZERO, True: ZERO}
            for line, qty in credited:
                # Same proration as the return's credit note itself.
                amount = (
                    line.ex_vat
                    if qty == line.qty
                    else (line.ex_vat * qty / line.qty).quantize(CENT, rounding=ROUND_HALF_UP)
                )
                split[line.exclude_from_commission] += amount
            out.append(
                (
                    CommissionDocument(
                        kind="credit_note",
                        id=note.id,
                        number=note.credit_note_number,
                        invoice_id=invoice.id,
                        invoice_number=invoice.invoice_number,
                        issue_date=note.issue_date,
                        customer_name=customer_name,
                        commissionable_ex_vat=split[False],
                        excluded_ex_vat=split[True],
                    ),
                    invoice.sales_staff_id,
                )
            )
        return out


def _row(
    staff_id: Optional[uuid.UUID],
    name: str,
    short_name: Optional[str],
    is_active: bool,
    rate: Decimal,
    docs: list[CommissionDocument],
) -> CommissionRow:
    invoices = [doc for doc in docs if doc.kind == "invoice"]
    credits = [doc for doc in docs if doc.kind == "credit_note"]
    commissionable = sum((doc.commissionable_ex_vat for doc in invoices), ZERO)
    deductions = sum((doc.commissionable_ex_vat for doc in credits), ZERO)
    net = commissionable - deductions
    return CommissionRow(
        sales_staff_id=staff_id,
        name=name,
        short_name=short_name,
        is_active=is_active,
        commission_rate=rate,
        invoice_count=len(invoices),
        commissionable_ex_vat=commissionable,
        excluded_ex_vat=sum((doc.excluded_ex_vat for doc in invoices), ZERO),
        credit_deductions=deductions,
        net_commissionable=net,
        commission=(net * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP),
        documents=docs,
    )
