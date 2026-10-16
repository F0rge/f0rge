"""Read-only views over imported customer/supplier detail and trading history."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import Numeric, Select, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.archive_credit_note import ArchiveCreditNote, ArchiveCreditNoteLine
from app.models.bill import Bill, BillLine
from app.models.cin7_party import CustomerAddress, CustomerContact, SupplierAddress, SupplierContact
from app.models.customer import Customer
from app.models.location import Location
from app.models.location_bin import BinStock, LocationBin
from app.models.sku import Sku
from app.models.sku_supplier_price import SkuSupplierPrice
from app.models.supplier import Supplier
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.permissions import STOCK_COST_VIEW
from app.schemas.page import Page, PageParams
from app.schemas.records import (
    AddressResponse,
    ContactResponse,
    PurchaseHistoryRow,
    SalesHistoryRow,
    StockByBinRow,
    SupplierPriceRow,
)
from app.services.permissions import PermissionService
from f0rge_core.exceptions import NotFoundError


def _like(value: str) -> str:
    return f"%{value.replace('%', '').replace('_', ' ')}%"


class RecordsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _can_view_cost(self, user_id: uuid.UUID) -> bool:
        return await PermissionService(self.db).has_permission(user_id, STOCK_COST_VIEW)

    async def _page(self, stmt: Select, params: PageParams) -> tuple[list, int]:
        total = await self.db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = (await self.db.execute(stmt.limit(params.limit).offset(params.offset))).all()
        return list(rows), int(total or 0)

    async def customer_addresses(self, customer_id: uuid.UUID) -> list[AddressResponse]:
        await self._require(Customer, customer_id, "Customer not found")
        rows = await self.db.scalars(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == customer_id)
            .order_by(CustomerAddress.is_default.desc(), CustomerAddress.address_type)
        )
        return [AddressResponse.model_validate(row) for row in rows]

    async def customer_contacts(self, customer_id: uuid.UUID) -> list[ContactResponse]:
        await self._require(Customer, customer_id, "Customer not found")
        rows = await self.db.scalars(
            select(CustomerContact)
            .where(CustomerContact.customer_id == customer_id)
            .order_by(CustomerContact.is_default.desc(), CustomerContact.name)
        )
        return [ContactResponse.model_validate(row) for row in rows]

    async def supplier_addresses(self, supplier_id: uuid.UUID) -> list[AddressResponse]:
        await self._require(Supplier, supplier_id, "Supplier not found")
        rows = await self.db.scalars(
            select(SupplierAddress)
            .where(SupplierAddress.supplier_id == supplier_id)
            .order_by(SupplierAddress.is_default.desc(), SupplierAddress.address_type)
        )
        return [AddressResponse.model_validate(row) for row in rows]

    async def supplier_contacts(self, supplier_id: uuid.UUID) -> list[ContactResponse]:
        await self._require(Supplier, supplier_id, "Supplier not found")
        rows = await self.db.scalars(
            select(SupplierContact)
            .where(SupplierContact.supplier_id == supplier_id)
            .order_by(SupplierContact.is_default.desc(), SupplierContact.name)
        )
        return [ContactResponse.model_validate(row) for row in rows]

    async def supplier_prices(
        self,
        user_id: uuid.UUID,
        params: PageParams,
        supplier_id: Optional[uuid.UUID] = None,
        sku_id: Optional[uuid.UUID] = None,
    ) -> Page[SupplierPriceRow]:
        stmt = (
            select(SkuSupplierPrice, Supplier, Sku)
            .join(Supplier, Supplier.id == SkuSupplierPrice.supplier_id)
            .join(Sku, Sku.id == SkuSupplierPrice.sku_id)
            .order_by(Supplier.name, Sku.our_ref)
        )
        if supplier_id is not None:
            stmt = stmt.where(SkuSupplierPrice.supplier_id == supplier_id)
        if sku_id is not None:
            stmt = stmt.where(SkuSupplierPrice.sku_id == sku_id)
        if params.q:
            pattern = _like(params.q)
            stmt = stmt.where(
                or_(
                    Sku.our_ref.ilike(pattern),
                    Sku.name.ilike(pattern),
                    SkuSupplierPrice.supplier_sku.ilike(pattern),
                    Supplier.name.ilike(pattern),
                )
            )
        show_cost = await self._can_view_cost(user_id)
        rows, total = await self._page(stmt, params)
        items = [
            SupplierPriceRow(
                id=price.id,
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                sku_id=sku.id,
                our_ref=sku.our_ref,
                sku_name=sku.name,
                supplier_sku=price.supplier_sku,
                currency=supplier.default_currency,
                latest_price=price.latest_price if show_cost else None,
                fixed_price=price.fixed_price if show_cost else None,
            )
            for price, supplier, sku in rows
        ]
        return Page(items=items, total=total)

    async def sales_history(
        self,
        params: PageParams,
        customer_id: Optional[uuid.UUID] = None,
        sku_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> Page[SalesHistoryRow]:
        invoices = (
            select(
                literal("invoice").label("kind"),
                TaxInvoice.id.label("document_id"),
                TaxInvoice.invoice_number.label("document_number"),
                TaxInvoice.issue_date.label("issue_date"),
                TaxInvoice.customer_id.label("customer_id"),
                InvoiceLine.sku_id.label("sku_id"),
                InvoiceLine.description.label("description"),
                cast(InvoiceLine.qty, Numeric(14, 4)).label("qty"),
                InvoiceLine.ex_vat.label("ex_vat"),
                InvoiceLine.vat_amount.label("vat_amount"),
                InvoiceLine.inc_vat.label("inc_vat"),
            )
            .join(InvoiceLine, InvoiceLine.invoice_id == TaxInvoice.id)
            .where(TaxInvoice.is_archive.is_(True))
        )
        credits = select(
            literal("credit_note").label("kind"),
            ArchiveCreditNote.id,
            ArchiveCreditNote.document_number,
            ArchiveCreditNote.issue_date,
            ArchiveCreditNote.customer_id,
            ArchiveCreditNoteLine.sku_id,
            ArchiveCreditNoteLine.description,
            ArchiveCreditNoteLine.qty,
            ArchiveCreditNoteLine.ex_vat,
            ArchiveCreditNoteLine.vat_amount,
            ArchiveCreditNoteLine.inc_vat,
        ).join(ArchiveCreditNoteLine, ArchiveCreditNoteLine.credit_note_id == ArchiveCreditNote.id)
        lines = union_all(invoices, credits).subquery("lines")
        stmt = (
            select(lines, Customer.name.label("customer_name"), Sku.our_ref.label("our_ref"))
            .outerjoin(Customer, Customer.id == lines.c.customer_id)
            .outerjoin(Sku, Sku.id == lines.c.sku_id)
            .order_by(lines.c.issue_date.desc(), lines.c.document_number.desc())
        )
        if customer_id is not None:
            stmt = stmt.where(lines.c.customer_id == customer_id)
        if sku_id is not None:
            stmt = stmt.where(lines.c.sku_id == sku_id)
        if date_from is not None:
            stmt = stmt.where(lines.c.issue_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(lines.c.issue_date <= date_to)
        if params.q:
            pattern = _like(params.q)
            stmt = stmt.where(
                or_(
                    lines.c.document_number.ilike(pattern),
                    lines.c.description.ilike(pattern),
                    Customer.name.ilike(pattern),
                    Sku.our_ref.ilike(pattern),
                )
            )
        rows, total = await self._page(stmt, params)
        return Page(items=[SalesHistoryRow(**row._mapping) for row in rows], total=total)

    async def purchase_history(
        self,
        user_id: uuid.UUID,
        params: PageParams,
        supplier_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime.date] = None,
        date_to: Optional[datetime.date] = None,
    ) -> Page[PurchaseHistoryRow]:
        stmt = (
            select(Bill, BillLine, Supplier)
            .join(BillLine, BillLine.bill_id == Bill.id)
            .join(Supplier, Supplier.id == Bill.supplier_id)
            .where(Bill.is_archive.is_(True))
            .order_by(Bill.issue_date.desc(), Bill.bill_number, BillLine.sort_order)
        )
        if supplier_id is not None:
            stmt = stmt.where(Bill.supplier_id == supplier_id)
        if date_from is not None:
            stmt = stmt.where(Bill.issue_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Bill.issue_date <= date_to)
        if params.q:
            pattern = _like(params.q)
            stmt = stmt.where(
                or_(
                    Bill.bill_number.ilike(pattern),
                    BillLine.description.ilike(pattern),
                    Supplier.name.ilike(pattern),
                )
            )
        show_cost = await self._can_view_cost(user_id)
        rows, total = await self._page(stmt, params)
        items = [
            PurchaseHistoryRow(
                bill_id=bill.id,
                bill_number=bill.bill_number,
                issue_date=bill.issue_date,
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                description=line.description,
                qty=line.qty,
                currency=bill.currency,
                unit_amount=line.unit_amount if show_cost else None,
                amount_foreign=line.amount_foreign if show_cost else None,
                fx_rate_known=bill.fx_rate_known,
                bill_amount_zar=bill.amount_zar if show_cost and bill.fx_rate_known else None,
            )
            for bill, line, supplier in rows
        ]
        return Page(items=items, total=total)

    async def stock_by_bin(
        self,
        params: PageParams,
        location_id: Optional[uuid.UUID] = None,
    ) -> Page[StockByBinRow]:
        stmt = (
            select(
                Location.id.label("location_id"),
                Location.name.label("location_name"),
                LocationBin.id.label("bin_id"),
                LocationBin.code.label("bin_code"),
                Sku.id.label("sku_id"),
                Sku.our_ref.label("our_ref"),
                Sku.name.label("sku_name"),
                BinStock.on_hand.label("on_hand"),
            )
            .join(LocationBin, LocationBin.id == BinStock.bin_id)
            .join(Location, Location.id == LocationBin.location_id)
            .join(Sku, Sku.id == BinStock.sku_id)
            .where(BinStock.on_hand != 0)
            .order_by(Location.name, LocationBin.code, Sku.our_ref)
        )
        if location_id is not None:
            stmt = stmt.where(Location.id == location_id)
        if params.q:
            pattern = _like(params.q)
            stmt = stmt.where(or_(Sku.our_ref.ilike(pattern), Sku.name.ilike(pattern)))
        rows, total = await self._page(stmt, params)
        return Page(items=[StockByBinRow(**row._mapping) for row in rows], total=total)

    async def _require(self, model: type, row_id: uuid.UUID, message: str) -> None:
        if await self.db.get(model, row_id) is None:
            raise NotFoundError(message)
