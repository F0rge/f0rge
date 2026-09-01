from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.proforma import ProformaCRUD
from app.crud.purchase_order import LocationStockCRUD, PurchaseOrderCRUD, SkuStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.supplier import SupplierCRUD
from app.models.inventory import LocationStock, SkuStock
from app.models.purchase_order import (
    LandingBill,
    LandingBillKind,
    PoLine,
    PurchaseOrder,
    PurchaseOrderStatus,
)
from app.schemas.purchase_order import (
    LandingBillResponse,
    PoLineResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    ReceiveRequest,
)
from app.services.object_storage import save_bytes
from app.services.packing_sheet import (
    build_packing_sheet_pdf,
    compute_landed_unit_costs,
    convert_bill_to_zar,
)
from app.services.suppliers import SupplierService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class PurchaseOrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PurchaseOrderCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.proforma_crud = ProformaCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.sku_stock_crud = SkuStockCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.location_crud = LocationCRUD(db)

    async def list(self) -> list[PurchaseOrderResponse]:
        orders = await self.crud.list_all()
        return [self._to_response(po) for po in orders]

    async def get(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        return self._to_response(po)

    async def create(self, data: PurchaseOrderCreate) -> PurchaseOrderResponse:
        supplier = await self.supplier_crud.get_by_id(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")

        if data.proforma_id is not None:
            proforma = await self.proforma_crud.get_by_id(data.proforma_id)
            if proforma is None:
                raise NotFoundError("Proforma not found")
            if proforma.supplier_id != data.supplier_id:
                raise ValidationError("Proforma must belong to the same supplier")

        if not data.lines:
            raise ValidationError("At least one line is required")

        sku_ids = {line.sku_id for line in data.lines}
        if len(sku_ids) != len(data.lines):
            raise ValidationError("Duplicate SKU lines are not allowed")

        for line in data.lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")

        po_number = await self.crud.get_next_po_number()
        po = PurchaseOrder(
            po_number=po_number,
            supplier_id=data.supplier_id,
            proforma_id=data.proforma_id,
            status=PurchaseOrderStatus.OPEN,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(po)
            for line in data.lines:
                po_line = PoLine(
                    po_id=po.id,
                    sku_id=line.sku_id,
                    qty=line.qty,
                    factory_unit_amount=line.factory_unit_amount,
                )
                await self.crud.add_and_flush(po_line)

        reloaded = await self._get_po_or_404(po.id)
        return self._to_response(reloaded)

    async def mark_on_water(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        if po.status != PurchaseOrderStatus.OPEN:
            raise ConflictError("Purchase order is not open")

        async with unit_of_work(self.db):
            po.status = PurchaseOrderStatus.ON_WATER
            for line in po.lines:
                stock = await self.sku_stock_crud.get_by_sku_id(line.sku_id)
                if stock is None:
                    stock = SkuStock(sku_id=line.sku_id, on_order=0)
                    await self.sku_stock_crud.add_and_flush(stock)
                stock.on_order += line.qty

        reloaded = await self._get_po_or_404(po_id)
        return self._to_response(reloaded)

    async def land(
        self,
        po_id: uuid.UUID,
        fx_to_zar: Decimal,
        factory_invoice_number: str,
        factory_amount: Decimal,
        factory_currency: Optional[str],
        factory_file: UploadFile,
        freight_invoice_number: str,
        freight_amount: Decimal,
        freight_currency: str,
        freight_file: UploadFile,
        clearance_invoice_number: str,
        clearance_amount: Decimal,
        clearance_currency: str,
        clearance_file: UploadFile,
    ) -> PurchaseOrderResponse:
        if fx_to_zar <= 0:
            raise ValidationError("fx_to_zar must be positive")

        po = await self._get_po_or_404(po_id)
        if po.status != PurchaseOrderStatus.ON_WATER:
            raise ConflictError("Purchase order must be on water to land")

        supplier = po.supplier
        factory_cur = SupplierService.normalize_currency(
            factory_currency or supplier.default_currency
        )
        freight_cur = SupplierService.normalize_currency(freight_currency)
        clearance_cur = SupplierService.normalize_currency(clearance_currency)

        factory_pdf = await factory_file.read()
        freight_pdf = await freight_file.read()
        clearance_pdf = await clearance_file.read()
        if not factory_pdf or not freight_pdf or not clearance_pdf:
            raise ValidationError("All three bill PDFs are required")

        factory_zar = convert_bill_to_zar(factory_amount, factory_cur, fx_to_zar)
        freight_zar = convert_bill_to_zar(freight_amount, freight_cur, fx_to_zar)
        clearance_zar = convert_bill_to_zar(clearance_amount, clearance_cur, fx_to_zar)

        line_inputs = [(line.qty, line.factory_unit_amount) for line in po.lines]
        unit_costs = compute_landed_unit_costs(
            line_inputs,
            factory_zar,
            freight_zar,
            clearance_zar,
        )

        bill_specs = [
            (
                LandingBillKind.FACTORY,
                factory_invoice_number,
                factory_amount,
                factory_cur,
                factory_pdf,
                "factory",
            ),
            (
                LandingBillKind.FREIGHT,
                freight_invoice_number,
                freight_amount,
                freight_cur,
                freight_pdf,
                "freight",
            ),
            (
                LandingBillKind.CLEARANCE,
                clearance_invoice_number,
                clearance_amount,
                clearance_cur,
                clearance_pdf,
                "clearance",
            ),
        ]

        async with unit_of_work(self.db):
            po.fx_to_zar = fx_to_zar
            po.status = PurchaseOrderStatus.LANDED

            for line, unit_cost in zip(po.lines, unit_costs):
                if unit_cost <= 0:
                    raise ValidationError("Computed unit cost must be positive")
                line.unit_cost_zar = unit_cost

            for kind, invoice_number, amount, currency, pdf_bytes, kind_slug in bill_specs:
                bill_id = uuid.uuid4()
                relative_path = f"landing-bills/{po_id}/{kind_slug}-{bill_id}.pdf"
                storage_key = await asyncio.to_thread(save_bytes, relative_path, pdf_bytes)

                bill = LandingBill(
                    po_id=po_id,
                    kind=kind,
                    invoice_number=invoice_number,
                    amount=amount,
                    currency=currency,
                    pdf_storage_key=storage_key,
                )
                await self.crud.add_and_flush(bill)

        reloaded = await self._get_po_or_404(po_id)
        return self._to_response(reloaded)

    async def packing_sheet(self, po_id: uuid.UUID) -> Response:
        po = await self._get_po_or_404(po_id)
        lines_data = [
            (
                line.sku.our_ref,
                line.sku.our_barcode,
                line.sku.name,
                line.sku.fabric,
                line.qty,
            )
            for line in po.lines
        ]
        pdf_bytes = build_packing_sheet_pdf(po.po_number, lines_data)

        relative_path = f"packing-sheets/{po_id}.pdf"
        try:
            await asyncio.to_thread(save_bytes, relative_path, pdf_bytes)
        except FileExistsError:
            pass

        return Response(content=pdf_bytes, media_type="application/pdf")

    async def receive(self, data: ReceiveRequest) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(data.purchase_order_id)

        if po.status == PurchaseOrderStatus.RECEIVED:
            raise ConflictError("Purchase order already received")

        if po.status != PurchaseOrderStatus.LANDED:
            raise ConflictError("Landed cost is required before receive")

        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot receive into archived location")

        async with unit_of_work(self.db):
            po.status = PurchaseOrderStatus.RECEIVED
            po.received_location_id = data.location_id

            for line in po.lines:
                stock = await self.sku_stock_crud.get_by_sku_id(line.sku_id)
                if stock is None:
                    raise ConflictError("SKU stock record not found")
                if stock.on_order < line.qty:
                    raise ConflictError("On-order quantity insufficient")
                stock.on_order -= line.qty

                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    line.sku_id,
                    data.location_id,
                )
                if loc_stock is None:
                    loc_stock = LocationStock(
                        sku_id=line.sku_id,
                        location_id=data.location_id,
                        on_hand=0,
                    )
                    await self.location_stock_crud.add_and_flush(loc_stock)

                old_on_hand = loc_stock.on_hand
                old_cost = loc_stock.unit_cost_zar
                incoming_qty = line.qty
                incoming_cost = line.unit_cost_zar
                new_on_hand = old_on_hand + incoming_qty
                if old_on_hand == 0 or old_cost is None:
                    blended = incoming_cost
                else:
                    blended = (old_on_hand * old_cost + incoming_qty * incoming_cost) / new_on_hand
                loc_stock.on_hand = new_on_hand
                loc_stock.unit_cost_zar = blended

        reloaded = await self._get_po_or_404(data.purchase_order_id)
        return self._to_response(reloaded)

    async def _get_po_or_404(self, po_id: uuid.UUID) -> PurchaseOrder:
        po = await self.crud.get_by_id(po_id)
        if po is None:
            raise NotFoundError("Purchase order not found")
        return po

    @staticmethod
    def _to_response(po: PurchaseOrder) -> PurchaseOrderResponse:
        lines = [
            PoLineResponse(
                id=line.id,
                sku_id=line.sku_id,
                our_ref=line.sku.our_ref,
                our_barcode=line.sku.our_barcode,
                name=line.sku.name,
                fabric=line.sku.fabric,
                qty=line.qty,
                factory_unit_amount=line.factory_unit_amount,
                unit_cost_zar=line.unit_cost_zar,
            )
            for line in po.lines
        ]
        bills = [
            LandingBillResponse(
                kind=bill.kind.value,
                invoice_number=bill.invoice_number,
                amount=bill.amount,
                currency=bill.currency,
            )
            for bill in po.bills
        ]
        return PurchaseOrderResponse(
            id=po.id,
            po_number=po.po_number,
            status=po.status.value,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier.name,
            proforma_id=po.proforma_id,
            fx_to_zar=po.fx_to_zar,
            lines=lines,
            bills=bills,
            received_location_id=po.received_location_id,
            created_at=po.created_at,
            updated_at=po.updated_at,
        )
