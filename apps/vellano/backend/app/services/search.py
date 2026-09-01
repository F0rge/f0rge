from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.purchase_order import PurchaseOrder
from app.models.sku import Sku
from app.models.tax_invoice import TaxInvoice
from app.schemas.search import (
    InvoiceSearchHit,
    PurchaseOrderSearchHit,
    SearchResponse,
    SkuSearchHit,
)
from f0rge_core.exceptions import ValidationError


class SearchService:
    MAX_RESULTS = 20

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, q: str) -> SearchResponse:
        term = q.strip()
        if not term:
            raise ValidationError("Search query is required")

        pattern = f"%{term}%"

        sku_result = await self.db.execute(
            select(Sku)
            .where(
                or_(
                    Sku.our_ref.ilike(pattern),
                    Sku.our_barcode.ilike(pattern),
                    Sku.name.ilike(pattern),
                )
            )
            .order_by(Sku.our_ref)
            .limit(self.MAX_RESULTS)
        )
        skus = [
            SkuSearchHit(
                id=sku.id,
                our_ref=sku.our_ref,
                our_barcode=sku.our_barcode,
                name=sku.name,
            )
            for sku in sku_result.scalars().all()
        ]

        po_result = await self.db.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.supplier))
            .where(PurchaseOrder.po_number.ilike(pattern))
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
            .where(TaxInvoice.invoice_number.ilike(pattern))
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
