from __future__ import annotations

import asyncio
import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.proforma import ProformaCRUD
from app.crud.purchase_order import PurchaseOrderCRUD, SkuStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.supplier import SupplierCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import UserCRUD
from app.models.inventory import SkuStock
from app.models.purchase_order import (
    LandingBill,
    LandingBillKind,
    PoLine,
    PurchaseOrder,
    PurchaseOrderStatus,
)
from app.models.supplier import Supplier
from app.schemas.page import Page, PageParams
from app.models.sku_supplier_price import SkuSupplierPrice
from app.schemas.purchase_order import (
    LandingBillResponse,
    PoLineCreate,
    PoLineResponse,
    PoLineSkuCreate,
    PoLineWrite,
    PurchaseOrderCreate,
    PurchaseOrderLinesUpdate,
    PurchaseOrderListItem,
    PurchaseOrderResponse,
    ReceiveRequest,
)
from app.schemas.sku import SkuCreate, SkuUpdate
from app.services.skus import SkuService
from app.models.unit_cost_audit import UnitCostAuditSource
from app.services.books_periods import assert_date_postable
from app.services.cost_audit import CostAuditService
from app.services.object_storage import save_bytes
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.packing_sheet import (
    build_packing_sheet_pdf,
    compute_landed_unit_costs,
    convert_bill_to_zar,
)
from app.services.purchase_order_pdf import PurchaseOrderPdfLine, build_purchase_order_pdf
from app.services.settings import SettingsService
from app.services.suppliers import SupplierService
from app.permissions import USERS_MANAGE
from app.services.permissions import PermissionService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _as_aware_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


def _stamp_first(po: PurchaseOrder, field: str, when: datetime.datetime) -> None:
    if getattr(po, field) is None:
        setattr(po, field, when)


class PurchaseOrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PurchaseOrderCRUD(db)
        self.supplier_crud = SupplierCRUD(db)
        self.proforma_crud = ProformaCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.sku_stock_crud = SkuStockCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.cost_audit = CostAuditService(db)
        self.stock_movements = StockMovementService(db)
        self.user_crud = UserCRUD(db)

    async def list(
        self,
        params: PageParams,
        status: Optional[PurchaseOrderStatus] = None,
        needs_skus: bool = False,
    ) -> Page[PurchaseOrderListItem]:
        orders, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            status=status,
            needs_skus=needs_skus,
        )
        return Page(
            items=[self._to_list_item(po) for po in orders],
            total=total,
        )

    async def get(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        return self._to_response(po)

    async def create(self, data: PurchaseOrderCreate, user_id: uuid.UUID) -> PurchaseOrderResponse:
        supplier = await self.supplier_crud.get_by_id(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier not found")

        if data.proforma_id is not None:
            proforma = await self.proforma_crud.get_by_id(data.proforma_id)
            if proforma is None:
                raise NotFoundError("Proforma not found")
            if proforma.supplier_id != data.supplier_id:
                raise ValidationError("Proforma must belong to the same supplier")

        await self._validate_line_writes(data.lines)
        resolved_codes = [
            await self._resolved_supplier_code(data.supplier_id, line.sku_id, line.supplier_code)
            for line in data.lines
        ]

        total_zar = await self._factory_total_zar(supplier, data.lines)
        create_status = await self._resolve_create_status(user_id, total_zar)
        if data.submit_for_approval or any(line.sku_id is None for line in data.lines):
            create_status = PurchaseOrderStatus.PENDING_APPROVAL

        po = PurchaseOrder(
            po_number="",
            supplier_id=data.supplier_id,
            proforma_id=data.proforma_id,
            supplier_ref=_blank_to_none(data.supplier_ref),
            notes=_blank_to_none(data.notes),
            status=create_status,
        )

        async with unit_of_work(self.db):
            po.po_number = await self.crud.get_next_po_number()
            await self.crud.add_and_flush(po)
            _stamp_first(po, "ordered_at", _as_aware_utc(po.created_at))
            for line, supplier_code in zip(data.lines, resolved_codes):
                po_line = _po_line_from_write(po.id, line, supplier_code)
                await self.crud.add_and_flush(po_line)

        reloaded = await self._get_po_or_404(po.id)
        return self._to_response(reloaded)

    async def update_pending(
        self,
        po_id: uuid.UUID,
        data: PurchaseOrderLinesUpdate,
    ) -> PurchaseOrderResponse:
        po = await self._reload(po_id)
        if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
            raise ConflictError("Only a purchase order waiting for approval can be edited.")
        await self._validate_line_writes(data.lines)
        resolved_codes = [
            await self._resolved_supplier_code(po.supplier_id, line.sku_id, line.supplier_code)
            for line in data.lines
        ]
        existing = {line.id: line for line in po.lines}
        seen: set[uuid.UUID] = set()
        async with unit_of_work(self.db):
            provided = data.model_fields_set
            if "supplier_ref" in provided:
                po.supplier_ref = _blank_to_none(data.supplier_ref)
            if "notes" in provided:
                po.notes = _blank_to_none(data.notes)
            for item, supplier_code in zip(data.lines, resolved_codes):
                if item.id is None:
                    await self.crud.add_and_flush(_po_line_from_write(po.id, item, supplier_code))
                    continue
                row = existing.get(item.id)
                if row is None:
                    raise NotFoundError("Purchase order line not found")
                _apply_line_write(row, item, supplier_code)
                seen.add(item.id)
            for line_id, row in existing.items():
                if line_id not in seen:
                    await self.db.delete(row)
        return self._to_response(await self._reload(po_id))

    async def create_line_sku(
        self,
        po_id: uuid.UUID,
        line_id: uuid.UUID,
        data: PoLineSkuCreate,
        user_id: uuid.UUID,
    ) -> PurchaseOrderResponse:
        po = await self._reload(po_id)
        if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
            raise ConflictError("Only a purchase order waiting for approval can be edited.")
        line = next((row for row in po.lines if row.id == line_id), None)
        if line is None:
            raise NotFoundError("Purchase order line not found")
        if line.sku_id is not None:
            raise ConflictError("This line already has a SKU.")
        supplier_code = _blank_to_none(line.supplier_code)
        skus = SkuService(self.db)
        created = await skus.create(
            SkuCreate(
                our_ref=data.our_ref,
                our_barcode=data.our_barcode,
                name=data.name,
                design=data.design,
                fabric=data.fabric,
                supplier_ref=None if supplier_code is None else supplier_code[:64],
                category=data.category,
            ),
            user_id,
        )
        await skus.update(created.id, SkuUpdate(preferred_supplier_id=po.supplier_id), user_id)
        po = await self._reload(po_id)
        current = next((row for row in po.lines if row.id == line_id), None)
        if current is None:
            raise NotFoundError("Purchase order line not found")
        price = SkuSupplierPrice(
            sku_id=created.id,
            supplier_id=po.supplier_id,
            supplier_sku=supplier_code,
            latest_price=current.factory_unit_amount,
        )
        async with unit_of_work(self.db):
            self.db.add(price)
            current.sku_id = created.id
            await self.db.flush()
        return self._to_response(await self._reload(po_id))

    async def approve(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
            raise ConflictError("Purchase order is not pending approval")
        _require_complete_lines(po, "approving")
        async with unit_of_work(self.db):
            po.status = PurchaseOrderStatus.OPEN
        reloaded = await self._get_po_or_404(po_id)
        return self._to_response(reloaded)

    async def reject(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
            raise ConflictError("Purchase order is not pending approval")
        async with unit_of_work(self.db):
            po.status = PurchaseOrderStatus.REJECTED
        reloaded = await self._get_po_or_404(po_id)
        return self._to_response(reloaded)

    async def mark_on_water(self, po_id: uuid.UUID) -> PurchaseOrderResponse:
        po = await self._get_po_or_404(po_id)
        _require_complete_lines(po, "this step")
        if po.status != PurchaseOrderStatus.OPEN:
            raise ConflictError("Purchase order is not open")

        async with unit_of_work(self.db):
            po.status = PurchaseOrderStatus.ON_WATER
            _stamp_first(po, "on_water_at", _utc_now())
            for line in po.lines:
                if line.sku_id is None:
                    continue
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
        user_id: uuid.UUID,
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
        _require_complete_lines(po, "this step")
        if po.status != PurchaseOrderStatus.ON_WATER:
            raise ConflictError("Purchase order must be on water to land")

        supplier = po.supplier
        factory_cur = SupplierService.normalize_currency(
            factory_currency or supplier.default_currency
        )
        freight_cur = SupplierService.normalize_currency(freight_currency)
        clearance_cur = SupplierService.normalize_currency(clearance_currency)

        factory_zar = convert_bill_to_zar(factory_amount, factory_cur, fx_to_zar)
        freight_zar = convert_bill_to_zar(freight_amount, freight_cur, fx_to_zar)
        clearance_zar = convert_bill_to_zar(clearance_amount, clearance_cur, fx_to_zar)
        line_factory_total = sum(
            (Decimal(line.qty) * line.factory_unit_amount for line in po.lines),
            Decimal(0),
        )
        line_zar = convert_bill_to_zar(line_factory_total, factory_cur, fx_to_zar)
        await self._assert_po_cap(user_id, max(factory_zar, line_zar))

        factory_pdf = await factory_file.read()
        freight_pdf = await freight_file.read()
        clearance_pdf = await clearance_file.read()
        if not factory_pdf or not freight_pdf or not clearance_pdf:
            raise ValidationError("All three bill PDFs are required")

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
            _stamp_first(po, "landed_at", _utc_now())

            for line, unit_cost in zip(po.lines, unit_costs):
                if unit_cost <= 0:
                    raise ValidationError("Computed unit cost must be positive")
                line.unit_cost_zar = unit_cost
                await self.cost_audit.record(
                    sku_id=line.sku_id,
                    new_cost_zar=unit_cost,
                    changed_by_user_id=user_id,
                    source=UnitCostAuditSource.LAND,
                    old_cost_zar=None,
                    po_id=po_id,
                    po_line_id=line.id,
                    note=f"Landed on {po.po_number}",
                )

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
        _require_complete_lines(po, "this step")
        lines_data = [
            (
                line.sku.our_ref,
                line.sku.our_barcode,
                line.sku.name,
                line.sku.fabric,
                line.qty,
                line.sku.carton_count,
            )
            for line in po.lines
        ]
        seller = await SettingsService(self.db).build_seller_details()
        pdf_bytes = build_packing_sheet_pdf(po.po_number, lines_data, seller=seller)

        relative_path = f"packing-sheets/{po_id}.pdf"
        try:
            await asyncio.to_thread(save_bytes, relative_path, pdf_bytes)
        except FileExistsError:
            pass

        return Response(content=pdf_bytes, media_type="application/pdf")

    async def purchase_order_pdf(self, po_id: uuid.UUID) -> Response:
        po = await self._get_po_or_404(po_id)
        if po.status == PurchaseOrderStatus.REJECTED:
            raise ConflictError("A rejected purchase order cannot be downloaded.")
        seller = await SettingsService(self.db).build_seller_details()
        currency = SupplierService.normalize_currency(po.supplier.default_currency)
        stamp = po.ordered_at or po.created_at
        po_date = _as_aware_utc(stamp).strftime("%Y-%m-%d")
        lines: list[PurchaseOrderPdfLine] = []
        for line in po.lines:
            lines.append(
                PurchaseOrderPdfLine(
                    supplier_code=await self._supplier_code_for_pdf(po, line),
                    description=_line_description(line),
                    our_ref=None if line.sku is None else line.sku.our_ref,
                    fabric=None if line.sku is None else _supplier_facing_fabric(line.sku.fabric),
                    notes=_blank_to_none(line.notes),
                    qty=line.qty,
                    unit_price=line.factory_unit_amount,
                )
            )
        pdf_bytes = build_purchase_order_pdf(
            po_number=po.po_number,
            po_date=po_date,
            status_label=_STATUS_LABELS[po.status],
            draft=po.status == PurchaseOrderStatus.PENDING_APPROVAL,
            supplier_name=po.supplier.name,
            supplier_ref=_blank_to_none(po.supplier_ref),
            currency=currency,
            notes=_blank_to_none(po.notes),
            lines=lines,
            seller=seller,
        )
        filename = f"{po.po_number}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def receive(self, data: ReceiveRequest, user_id: uuid.UUID) -> PurchaseOrderResponse:
        await assert_date_postable(self.db, datetime.date.today())
        await StocktakeService(self.db).assert_location_unlocked(data.location_id)
        po = await self._get_po_or_404(data.purchase_order_id)
        _require_complete_lines(po, "this step")

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
            _stamp_first(po, "received_at", _utc_now())

            for line in po.lines:
                if line.sku_id is None:
                    continue
                stock = await self.sku_stock_crud.get_by_sku_id(line.sku_id)
                if stock is None:
                    raise ConflictError("SKU stock record not found")
                if stock.on_order < line.qty:
                    raise ConflictError("On-order quantity insufficient")
                stock.on_order -= line.qty
                assert line.unit_cost_zar is not None

                await self.stock_movements.apply_incoming_qty(
                    sku_id=line.sku_id,
                    location_id=data.location_id,
                    qty=line.qty,
                    unit_cost_zar=line.unit_cost_zar,
                    user_id=user_id,
                    source=UnitCostAuditSource.RECEIVE,
                    note=f"Received {po.po_number} into location",
                    bin_id=data.bin_id,
                    po_id=po.id,
                    po_line_id=line.id,
                )

        reloaded = await self._get_po_or_404(data.purchase_order_id)
        return self._to_response(reloaded)

    async def _resolved_supplier_code(
        self,
        supplier_id: uuid.UUID,
        sku_id: Optional[uuid.UUID],
        given: Optional[str],
    ) -> Optional[str]:
        """Keep a typed code. Otherwise fill from the factory's model code.

        Prefer sku_supplier_prices.supplier_sku for this PO's supplier. That is
        the code the factory itself uses (Cin7 import and "create SKU from a PO
        line" already write it), and one SKU can be bought from more than one
        factory. Fall back to skus.supplier_ref when this supplier has no code.
        """
        typed = _blank_to_none(given)
        if typed is not None or sku_id is None:
            return typed
        supplier_sku = (
            await self.db.execute(
                select(SkuSupplierPrice.supplier_sku).where(
                    SkuSupplierPrice.sku_id == sku_id,
                    SkuSupplierPrice.supplier_id == supplier_id,
                )
            )
        ).scalar_one_or_none()
        from_supplier = _blank_to_none(supplier_sku)
        if from_supplier is not None:
            return from_supplier
        sku = await self.sku_crud.get_by_id(sku_id)
        if sku is None:
            return None
        return _blank_to_none(sku.supplier_ref)

    async def _supplier_code_for_pdf(self, po: PurchaseOrder, line: PoLine) -> Optional[str]:
        """Show the stored code. Look one up for older lines that were never filled.

        Reading the catalogue here does not write the line, so existing POs stay
        as they are until someone edits them.
        """
        stored = _blank_to_none(line.supplier_code)
        if stored is not None or line.sku_id is None:
            return stored
        return await self._resolved_supplier_code(po.supplier_id, line.sku_id, None)

    async def _validate_line_writes(self, lines: list[PoLineCreate] | list[PoLineWrite]) -> None:
        if not lines:
            raise ValidationError("At least one line is required")
        sku_ids = [line.sku_id for line in lines if line.sku_id is not None]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValidationError("Duplicate SKU lines are not allowed")
        for line in lines:
            if line.sku_id is None and not (line.description or "").strip():
                raise ValidationError("A line without a SKU needs a description.")
            if line.sku_id is not None:
                sku = await self.sku_crud.get_by_id(line.sku_id)
                if sku is None:
                    raise NotFoundError("SKU not found")

    async def _reload(self, po_id: uuid.UUID) -> PurchaseOrder:
        """Re-read lines from the database.

        The test session keeps loaded relationships after commit. A later
        request in that same session would otherwise edit a stale line list
        and miss a SKU that was just created.
        """
        current = await self.crud.get_by_id(po_id)
        if current is not None:
            for line in list(current.lines):
                if sa_inspect(line).persistent:
                    self.db.expire(line, ["sku"])
            self.db.expire(current, ["lines"])
        return await self._get_po_or_404(po_id)

    async def _get_po_or_404(self, po_id: uuid.UUID) -> PurchaseOrder:
        po = await self.crud.get_by_id(po_id)
        if po is None:
            raise NotFoundError("Purchase order not found")
        return po

    async def _factory_total_zar(
        self,
        supplier: Supplier,
        lines: list[PoLineCreate],
    ) -> Optional[Decimal]:
        factory_total = sum(
            (Decimal(line.qty) * line.factory_unit_amount for line in lines),
            Decimal(0),
        )
        currency = SupplierService.normalize_currency(supplier.default_currency)
        if currency == "ZAR":
            return factory_total
        fx = await self.crud.latest_fx_to_zar_for_supplier(supplier.id)
        if fx is None:
            return None
        return convert_bill_to_zar(factory_total, currency, fx)

    async def _resolve_create_status(
        self,
        user_id: uuid.UUID,
        total_zar: Optional[Decimal],
    ) -> PurchaseOrderStatus:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        team_settings = await TeamSettingsCRUD(self.db).get_or_create_for_team(user.team_id)
        threshold = team_settings.po_approval_threshold_zar
        if threshold is None:
            return PurchaseOrderStatus.OPEN
        if total_zar is not None and total_zar <= threshold:
            return PurchaseOrderStatus.OPEN
        if await PermissionService(self.db).has_permission(user_id, USERS_MANAGE):
            return PurchaseOrderStatus.OPEN
        return PurchaseOrderStatus.PENDING_APPROVAL

    async def _assert_po_cap(self, user_id: uuid.UUID, total_zar: Optional[Decimal]) -> None:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        team_settings = await TeamSettingsCRUD(self.db).get_or_create_for_team(user.team_id)
        threshold = team_settings.po_approval_threshold_zar
        if threshold is None:
            return
        if total_zar is not None and total_zar <= threshold:
            return
        if await PermissionService(self.db).has_permission(user_id, USERS_MANAGE):
            return
        if total_zar is None:
            raise ConflictError(
                "Cannot convert PO total to ZAR without a prior FX rate for this supplier"
            )
        raise ConflictError(f"Purchase order total exceeds approval threshold ({threshold} ZAR)")

    @staticmethod
    def _to_list_item(po: PurchaseOrder) -> PurchaseOrderListItem:
        return PurchaseOrderListItem(
            id=po.id,
            po_number=po.po_number,
            status=po.status.value,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier.name,
            proforma_id=po.proforma_id,
            supplier_ref=po.supplier_ref,
            notes=po.notes,
            fx_to_zar=po.fx_to_zar,
            line_count=len(po.lines),
            needs_sku_count=_needs_sku_count(po),
            received_location_id=po.received_location_id,
            ordered_at=po.ordered_at,
            on_water_at=po.on_water_at,
            landed_at=po.landed_at,
            received_at=po.received_at,
            created_at=po.created_at,
            updated_at=po.updated_at,
        )

    @staticmethod
    def _to_response(po: PurchaseOrder) -> PurchaseOrderResponse:
        lines = [_line_response(line) for line in po.lines]
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
            supplier_ref=po.supplier_ref,
            notes=po.notes,
            fx_to_zar=po.fx_to_zar,
            needs_sku_count=_needs_sku_count(po),
            lines=lines,
            bills=bills,
            received_location_id=po.received_location_id,
            ordered_at=po.ordered_at,
            on_water_at=po.on_water_at,
            landed_at=po.landed_at,
            received_at=po.received_at,
            created_at=po.created_at,
            updated_at=po.updated_at,
        )


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _needs_sku_count(po: PurchaseOrder) -> int:
    return sum(1 for line in po.lines if line.sku_id is None)


def _require_complete_lines(po: PurchaseOrder, step: str) -> None:
    missing = _needs_sku_count(po)
    if missing == 0:
        return
    noun = "line" if missing == 1 else "lines"
    raise ValidationError(
        f"This purchase order still has {missing} {noun} without a SKU. "
        f"Fill those in before {step}."
    )


_STATUS_LABELS = {
    PurchaseOrderStatus.PENDING_APPROVAL: "Pending approval",
    PurchaseOrderStatus.REJECTED: "Rejected",
    PurchaseOrderStatus.OPEN: "Open",
    PurchaseOrderStatus.ON_WATER: "On water",
    PurchaseOrderStatus.LANDED: "Landed",
    PurchaseOrderStatus.RECEIVED: "Received",
}


def _supplier_facing_fabric(fabric: Optional[str]) -> Optional[str]:
    """Table-top colour and upholstery share skus.fabric. '-' is the placeholder."""
    cleaned = (fabric or "").strip()
    if not cleaned or cleaned == "-":
        return None
    return cleaned


def _line_description(line: PoLine) -> str:
    description = _blank_to_none(line.description)
    if description is not None:
        return description
    if line.sku is not None and line.sku.name:
        return line.sku.name
    return "—"


def _po_line_from_write(
    po_id: uuid.UUID,
    line: PoLineCreate | PoLineWrite,
    supplier_code: Optional[str],
) -> PoLine:
    return PoLine(
        po_id=po_id,
        sku_id=line.sku_id,
        supplier_code=supplier_code,
        description=_blank_to_none(line.description),
        notes=_blank_to_none(line.notes),
        qty=line.qty,
        factory_unit_amount=line.factory_unit_amount,
    )


def _apply_line_write(row: PoLine, line: PoLineWrite, supplier_code: Optional[str]) -> None:
    row.sku_id = line.sku_id
    row.supplier_code = supplier_code
    row.description = _blank_to_none(line.description)
    row.notes = _blank_to_none(line.notes)
    row.qty = line.qty
    row.factory_unit_amount = line.factory_unit_amount


def _line_response(line: PoLine) -> PoLineResponse:
    sku = line.sku
    return PoLineResponse(
        id=line.id,
        sku_id=line.sku_id,
        our_ref=None if sku is None else sku.our_ref,
        our_barcode=None if sku is None else sku.our_barcode,
        name=(line.description or "Needs a SKU") if sku is None else sku.name,
        fabric=None if sku is None else sku.fabric,
        supplier_code=line.supplier_code,
        description=line.description,
        notes=line.notes,
        needs_sku=line.sku_id is None,
        qty=line.qty,
        factory_unit_amount=line.factory_unit_amount,
        unit_cost_zar=line.unit_cost_zar,
    )
