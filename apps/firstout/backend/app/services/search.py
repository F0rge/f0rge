from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.sku import escape_like
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.models.purchase_order import PurchaseOrder
from app.models.sku import Sku
from app.models.tax_invoice import TaxInvoice
from app.schemas.search import (
    InvoiceSearchHit,
    PurchaseOrderSearchHit,
    SearchResponse,
    SkuSearchHit,
)
from app.services.stock_availability import StockAvailability
from app.services.vat import current_vat_rate, inc_vat_or_none
from f0rge_core.exceptions import ValidationError


class SearchService:
    MAX_RESULTS = 20

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, q: str) -> SearchResponse:
        term = q.strip()
        if not term:
            raise ValidationError("Search query is required")

        # A literal % or _ in the term matches itself, not any text.
        pattern = f"%{escape_like(term)}%"

        sku_result = await self.db.execute(
            select(Sku)
            .where(Sku.is_archived.is_(False))
            .where(
                or_(
                    Sku.our_ref.ilike(pattern, escape="\\"),
                    Sku.our_barcode.ilike(pattern, escape="\\"),
                    Sku.name.ilike(pattern, escape="\\"),
                )
            )
            .order_by(Sku.our_ref)
            .limit(self.MAX_RESULTS)
        )
        sku_rows = list(sku_result.scalars().all())
        skus = await self._sku_hits(sku_rows)

        po_result = await self.db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.supplier))
            .where(PurchaseOrder.po_number.ilike(pattern, escape="\\"))
            .order_by(PurchaseOrder.po_number)
            .limit(self.MAX_RESULTS)
        )
        purchase_orders = [
            PurchaseOrderSearchHit(
                id=po.id,
                po_number=po.po_number,
                status=po.status.value,
                supplier_name=po.supplier.name,
            )
            for po in po_result.scalars().all()
        ]

        invoice_result = await self.db.execute(
            select(TaxInvoice)
            .options(selectinload(TaxInvoice.customer))
            .where(TaxInvoice.invoice_number.ilike(pattern, escape="\\"))
            .order_by(TaxInvoice.invoice_number)
            .limit(self.MAX_RESULTS)
        )
        invoices = [
            InvoiceSearchHit(
                id=inv.id,
                invoice_number=inv.invoice_number,
                customer_name=inv.customer.name,
            )
            for inv in invoice_result.scalars().all()
        ]

        return SearchResponse(
            q=term,
            skus=skus,
            purchase_orders=purchase_orders,
            invoices=invoices,
        )

    async def _sku_hits(self, rows: list[Sku]) -> list[SkuSearchHit]:
        if not rows:
            return []
        ids = [sku.id for sku in rows]
        now = datetime.datetime.now(datetime.timezone.utc)
        available = await StockAvailability(self.db).company_available(ids, now)
        kits = await SkuBomLineCRUD(self.db).parent_ids_with_bom(ids)
        vat_rate = await current_vat_rate(self.db)
        return [
            SkuSearchHit(
                id=sku.id,
                our_ref=sku.our_ref,
                our_barcode=sku.our_barcode,
                name=sku.name,
                category=sku.category,
                has_photo=bool(sku.gallery_photo_keys or sku.photo_storage_key),
                retail_inc_vat=inc_vat_or_none(sku.retail_ex_vat, vat_rate),
                available=max(Decimal(0), available.get(sku.id, Decimal(0))),
                is_kit=sku.id in kits,
                sell_multiple=sku.sell_multiple,
                min_sell_qty=sku.min_sell_qty,
            )
            for sku in rows
        ]
