from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.delivery import DeliveryCRUD
from app.crud.layby import LaybyCRUD
from app.crud.location import LocationCRUD
from app.crud.pick import PickCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.transfer import TransferCRUD
from app.crud.user import UserCRUD
from app.models.delivery import DeliveryLine, DeliverySourceType
from app.models.layby import LaybyStatus
from app.models.location import LocationType
from app.models.pick import Pick, PickAllocation, PickLine, PickSourceType, PickStatus
from app.models.sku_bom_line import SkuBomLine
from app.models.transfer import TransferStatus
from app.schemas.delivery import DeliveryCreate
from app.schemas.pick import (
    PickComplete,
    PickConfirm,
    PickCreate,
    PickPreviewRequest,
    PickPreviewResponse,
    PickResponse,
    PickUpdate,
)
from app.schemas.transfer import TransferCreate, TransferLineCreate
from app.services.deliveries import DeliveriesService
from app.services.pick_allocator import (
    AllocationResult,
    ComponentNeed,
    LocationMeta,
    LocationStockRow,
    SuggestedAllocation,
    allocate,
    allocations_need_confirm,
    first_warehouse_id,
)
from app.services.pick_sheet import build_pick_sheet_pdf
from app.services.settings import parse_pick_priority
from app.services.transfers import TransferService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class PickService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = PickCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.bom_crud = SkuBomLineCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.settings_crud = TeamSettingsCRUD(db)
        self.user_crud = UserCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.layby_crud = LaybyCRUD(db)
        self.transfer_crud = TransferCRUD(db)
        self.delivery_crud = DeliveryCRUD(db)
        self.transfers = TransferService(db)
        self.deliveries = DeliveriesService(db)

    async def preview(self, data: PickPreviewRequest, user_id: uuid.UUID) -> PickPreviewResponse:
        kit, qty, needs = await self._explode_sku(data.sku_id, data.qty)
        result = await self._allocate(needs, user_id)
        return PickPreviewResponse(
            kit_sku_id=kit.id,
            kit_qty=qty,
            needs_confirm=result.needs_confirm,
            lines=await self._preview_lines(result),
        )

    async def create(self, data: PickCreate, user_id: uuid.UUID) -> PickResponse:
        if data.invoice_id is not None:
            origin = await self._origin_from_invoice(data.invoice_id)
        elif data.layby_id is not None:
            origin = await self._origin_from_layby(data.layby_id)
        else:
            assert data.sku_id is not None and data.qty is not None
            origin = await self._origin_from_till(data.sku_id, data.qty, data.customer_id)

        result = await self._allocate(origin.needs, user_id)
        lines = [
            PickLine(
                sku_id=line.sku_id,
                qty_needed=line.qty_needed,
                allocations=[
                    PickAllocation(location_id=item.location_id, qty=item.qty)
                    for item in line.allocations
                ],
            )
            for line in result.lines
        ]
        pick = Pick(
            number=await self.crud.get_next_pick_number(),
            source_type=origin.source_type,
            source_id=origin.source_id,
            kit_sku_id=origin.kit_sku_id,
            kit_qty=origin.kit_qty,
            status=PickStatus.DRAFT,
            customer_id=origin.customer_id,
            invoice_id=origin.invoice_id,
            lines=lines,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(pick)
        return await self.get(pick.id)

    async def list(self) -> list[PickResponse]:
        rows = await self.crud.list_all()
        return [await self._to_response(row) for row in rows]

    async def get(self, pick_id: uuid.UUID) -> PickResponse:
        return await self._to_response(await self._get_or_404(pick_id))

    async def update(self, pick_id: uuid.UUID, data: PickUpdate) -> PickResponse:
        pick = await self._get_or_404(pick_id)
        if pick.status != PickStatus.DRAFT:
            raise ConflictError("Pick is not a draft")

        incoming = {line.sku_id: line.allocations for line in data.lines}
        expected = {line.sku_id for line in pick.lines}
        if set(incoming.keys()) != expected:
            raise ValidationError("PATCH must include every pick line")

        stocks = await self._stock_rows(list(expected))
        on_hand = {
            (row.sku_id, row.location_id): row.on_hand for row in stocks if not row.is_archived
        }
        for line in pick.lines:
            replacements = incoming[line.sku_id]
            total = sum(item.qty for item in replacements)
            if total > line.qty_needed:
                raise ValidationError("Allocated qty exceeds need")
            seen: set[uuid.UUID] = set()
            new_allocs: list[PickAllocation] = []
            for item in replacements:
                if item.location_id in seen:
                    raise ValidationError("Duplicate allocation location")
                seen.add(item.location_id)
                available = on_hand.get((line.sku_id, item.location_id), 0)
                if item.qty > available:
                    raise ValidationError("Allocated qty exceeds on-hand")
                location = await self.location_crud.get_by_id(item.location_id)
                if location is None:
                    raise NotFoundError("Location not found")
                if location.is_archived:
                    raise ConflictError("Cannot allocate from archived location")
                new_allocs.append(PickAllocation(location_id=item.location_id, qty=item.qty))
            line.allocations.clear()
            line.allocations.extend(new_allocs)

        async with unit_of_work(self.db):
            await self.db.flush()
        return await self.get(pick_id)

    async def confirm(
        self,
        pick_id: uuid.UUID,
        data: PickConfirm,
        user_id: uuid.UUID,
    ) -> PickResponse:
        pick = await self._get_or_404(pick_id)
        if pick.status != PickStatus.DRAFT:
            raise ConflictError("Pick is not a draft")
        for line in pick.lines:
            allocated = sum(item.qty for item in line.allocations)
            if allocated != line.qty_needed:
                raise ValidationError("Confirm requires a full allocation")
        if await self._needs_confirm(pick) and not data.confirm_split:
            raise ConflictError("confirm_split required")
        async with unit_of_work(self.db):
            pick.status = PickStatus.CONFIRMED
        return await self.get(pick_id)

    async def complete(
        self,
        pick_id: uuid.UUID,
        data: PickComplete,
        user_id: uuid.UUID,
    ) -> PickResponse:
        pick = await self._get_or_404(pick_id)
        if pick.status != PickStatus.CONFIRMED:
            raise ConflictError("Pick is not confirmed")
        existing = await self.transfer_crud.list_by_pick_id(pick.id)
        if existing:
            raise ConflictError("Pick already has transfers")

        alloc_locations = {item.location_id for line in pick.lines for item in line.allocations}
        if not alloc_locations:
            raise ValidationError("Pick has no allocations")

        skip_transfers = False
        staging_id = data.staging_location_id
        if data.collect_from_showroom and len(alloc_locations) == 1:
            only_id = next(iter(alloc_locations))
            only = await self._active_location(only_id)
            if only.type == LocationType.SHOWROOM:
                staging_id = only.id
                skip_transfers = True

        if staging_id is None:
            staging_id = await self._default_staging(user_id)
        if staging_id is None:
            raise ValidationError("No warehouse staging location")
        await self._active_location(staging_id)

        if alloc_locations == {staging_id}:
            skip_transfers = True

        if skip_transfers:
            async with unit_of_work(self.db):
                pick.status = PickStatus.STAGED
                pick.staging_location_id = staging_id
            await self.ensure_delivery(pick.id, user_id)
            return await self.get(pick_id)

        grouped: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
        for line in pick.lines:
            for item in line.allocations:
                if item.location_id == staging_id:
                    continue
                grouped[item.location_id][line.sku_id] += item.qty
        for from_id, qty_by_sku in grouped.items():
            created = await self.transfers.create(
                TransferCreate(
                    from_location_id=from_id,
                    to_location_id=staging_id,
                    pick_id=pick.id,
                    lines=[
                        TransferLineCreate(sku_id=sku_id, qty=qty)
                        for sku_id, qty in qty_by_sku.items()
                    ],
                ),
                user_id,
            )
            await self.transfers.dispatch(created.id, user_id)

        async with unit_of_work(self.db):
            pick.status = PickStatus.PICKING
            pick.staging_location_id = staging_id
        return await self.get(pick_id)

    async def cancel(self, pick_id: uuid.UUID) -> PickResponse:
        pick = await self._get_or_404(pick_id)
        if pick.status not in (PickStatus.DRAFT, PickStatus.CONFIRMED):
            raise ConflictError("Pick cannot be cancelled")
        async with unit_of_work(self.db):
            pick.status = PickStatus.CANCELLED
        return await self.get(pick_id)

    async def serve_pdf(self, pick_id: uuid.UUID) -> Response:
        pick = await self._get_or_404(pick_id)
        sections_map: dict[str, list[tuple[str, str, int]]] = {}
        completeness: list[tuple[str, int, int]] = []
        for line in pick.lines:
            allocated = sum(item.qty for item in line.allocations)
            completeness.append((line.sku.name, allocated, line.qty_needed))
            for item in line.allocations:
                sections_map.setdefault(item.location.name, []).append(
                    (line.sku.our_ref, line.sku.name, item.qty)
                )
        customer_name = pick.customer.name if pick.customer is not None else None
        kit_label = f"{pick.kit_sku.our_ref} {pick.kit_sku.name} × {pick.kit_qty}"
        pdf_bytes = build_pick_sheet_pdf(
            pick_number=pick.number,
            customer_name=customer_name,
            kit_label=kit_label,
            sections=list(sections_map.items()),
            completeness=completeness,
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def stage_after_transfer_received(
        self,
        pick_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        pick = await self.crud.get_by_id(pick_id)
        if pick is None or pick.status in (PickStatus.STAGED, PickStatus.CANCELLED):
            return
        transfers = await self.transfer_crud.list_by_pick_id(pick_id)
        active = [row for row in transfers if row.status != TransferStatus.CANCELLED]
        if not active or any(row.status != TransferStatus.RECEIVED for row in active):
            return
        staging_id = pick.staging_location_id
        if staging_id is None and active:
            staging_id = active[0].to_location_id
        async with unit_of_work(self.db):
            pick.status = PickStatus.STAGED
            if staging_id is not None:
                pick.staging_location_id = staging_id
        await self.ensure_delivery(pick_id, user_id)

    async def ensure_delivery(self, pick_id: uuid.UUID, user_id: uuid.UUID) -> None:
        pick = await self._get_or_404(pick_id)
        if pick.status != PickStatus.STAGED:
            return
        location_id = pick.staging_location_id
        if location_id is None:
            return
        if pick.invoice_id is not None:
            existing = await self.delivery_crud.get_active_by_invoice_id(pick.invoice_id)
            if existing is not None:
                return
            source_type = DeliverySourceType.INVOICE
            invoice_id = pick.invoice_id
            layby_id = None
        elif pick.source_type == PickSourceType.LAYBY and pick.source_id is not None:
            existing = await self.delivery_crud.get_active_by_layby_id(pick.source_id)
            if existing is not None:
                return
            source_type = DeliverySourceType.LAYBY
            invoice_id = None
            layby_id = pick.source_id
        else:
            return
        overrides = [
            DeliveryLine(
                sku_id=line.sku_id,
                description=line.sku.name if line.sku.name else line.sku.our_ref,
                qty=line.qty_needed,
                sort_order=index,
            )
            for index, line in enumerate(pick.lines)
        ]
        await self.deliveries.create(
            DeliveryCreate(
                source_type=source_type,
                invoice_id=invoice_id,
                layby_id=layby_id,
                location_id=location_id,
            ),
            user_id,
            lines_override=overrides,
        )

    async def _origin_from_till(
        self,
        sku_id: uuid.UUID,
        qty: int,
        customer_id: Optional[uuid.UUID],
    ) -> "_PickOrigin":
        kit, kit_qty, needs = await self._explode_sku(sku_id, qty)
        if customer_id is not None:
            customer = await self.customer_crud.get_by_id(customer_id)
            if customer is None:
                raise NotFoundError("Customer not found")
        return _PickOrigin(
            source_type=PickSourceType.TILL,
            source_id=None,
            kit_sku_id=kit.id,
            kit_qty=kit_qty,
            customer_id=customer_id,
            invoice_id=None,
            needs=needs,
        )

    async def _origin_from_invoice(self, invoice_id: uuid.UUID) -> "_PickOrigin":
        invoice = await self.invoice_crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        if invoice.amount_paid != invoice.total_inc_vat:
            raise ValidationError("Invoice is not fully paid")
        kit_sku_id, kit_qty, needs = await self._explode_document_lines(
            [(line.sku_id, line.qty) for line in invoice.lines if line.sku_id is not None]
        )
        return _PickOrigin(
            source_type=PickSourceType.INVOICE,
            source_id=invoice.id,
            kit_sku_id=kit_sku_id,
            kit_qty=kit_qty,
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            needs=needs,
        )

    async def _origin_from_layby(self, layby_id: uuid.UUID) -> "_PickOrigin":
        layby = await self.layby_crud.get_by_id(layby_id)
        if layby is None:
            raise NotFoundError("Layby not found")
        if layby.status not in (LaybyStatus.OPEN, LaybyStatus.READY):
            raise ConflictError("Layby is not open")
        kit_sku_id, kit_qty, needs = await self._explode_document_lines(
            [(line.sku_id, line.qty) for line in layby.lines]
        )
        return _PickOrigin(
            source_type=PickSourceType.LAYBY,
            source_id=layby.id,
            kit_sku_id=kit_sku_id,
            kit_qty=kit_qty,
            customer_id=layby.customer_id,
            invoice_id=None,
            needs=needs,
        )

    async def _explode_document_lines(
        self,
        lines: list[tuple[uuid.UUID, int]],
    ) -> tuple[uuid.UUID, int, list[ComponentNeed]]:
        kit_qty_by_sku: dict[uuid.UUID, int] = {}
        bom_by_parent: dict[uuid.UUID, list[SkuBomLine]] = {}
        for sku_id, qty in lines:
            bom = await self.bom_crud.list_by_parent(sku_id)
            if not bom:
                continue
            kit_qty_by_sku[sku_id] = kit_qty_by_sku.get(sku_id, 0) + qty
            bom_by_parent[sku_id] = bom
        if not kit_qty_by_sku:
            raise ValidationError("Document has no kit lines")
        if len(kit_qty_by_sku) != 1:
            raise ValidationError("Pick supports one kit SKU")
        kit_sku_id, kit_qty = next(iter(kit_qty_by_sku.items()))
        needs_map: dict[uuid.UUID, int] = {}
        for parent_id, qty in kit_qty_by_sku.items():
            for bom in bom_by_parent[parent_id]:
                needs_map[bom.component_sku_id] = (
                    needs_map.get(bom.component_sku_id, 0) + bom.qty * qty
                )
        return (
            kit_sku_id,
            kit_qty,
            [ComponentNeed(sku_id=sku_id, qty_needed=qty) for sku_id, qty in needs_map.items()],
        )

    async def _explode_sku(
        self,
        sku_id: uuid.UUID,
        qty: int,
    ) -> tuple[object, int, list[ComponentNeed]]:
        sku = await self.sku_crud.get_by_id(sku_id)
        if sku is None:
            raise NotFoundError("SKU not found")
        bom = await self.bom_crud.list_by_parent(sku.id)
        if not bom:
            raise ValidationError("SKU is not a kit")
        needs = [
            ComponentNeed(sku_id=line.component_sku_id, qty_needed=line.qty * qty) for line in bom
        ]
        return sku, qty, needs

    async def _allocate(
        self,
        needs: list[ComponentNeed],
        user_id: uuid.UUID,
    ) -> AllocationResult:
        prefer, priority = await self._settings(user_id)
        stocks = await self._stock_rows([need.sku_id for need in needs])
        return allocate(needs, stocks, prefer, priority)

    async def _settings(self, user_id: uuid.UUID) -> tuple[bool, list[uuid.UUID]]:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        settings = await self.settings_crud.get_or_create_for_team(user.team_id)
        return bool(settings.always_prefer_warehouse), parse_pick_priority(settings.pick_priority)

    async def _stock_rows(self, sku_ids: list[uuid.UUID]) -> list[LocationStockRow]:
        locations = await self.location_crud.list_all()
        stocks = await self.location_stock_crud.list_for_sku_ids(sku_ids)
        by_key = {(row.sku_id, row.location_id): row for row in stocks}
        rows: list[LocationStockRow] = []
        for location in locations:
            for sku_id in sku_ids:
                stock = by_key.get((sku_id, location.id))
                rows.append(
                    LocationStockRow(
                        location_id=location.id,
                        sku_id=sku_id,
                        on_hand=stock.on_hand if stock is not None else 0,
                        location_type=location.type.value,
                        location_name=location.name,
                        is_archived=location.is_archived,
                    )
                )
        return rows

    async def _default_staging(self, user_id: uuid.UUID) -> Optional[uuid.UUID]:
        prefer, priority = await self._settings(user_id)
        locations = await self.location_crud.list_all()
        metas = [
            LocationMeta(
                location_id=location.id,
                location_type=location.type.value,
                location_name=location.name,
                is_archived=location.is_archived,
            )
            for location in locations
        ]
        return first_warehouse_id(metas, priority, prefer)

    async def _active_location(self, location_id: uuid.UUID):
        location = await self.location_crud.get_by_id(location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Location is archived")
        return location

    async def _needs_confirm(self, pick: Pick) -> bool:
        needs = [
            ComponentNeed(sku_id=line.sku_id, qty_needed=line.qty_needed) for line in pick.lines
        ]
        stocks = await self._stock_rows([line.sku_id for line in pick.lines])
        allocs = [
            SuggestedAllocation(sku_id=line.sku_id, location_id=item.location_id, qty=item.qty)
            for line in pick.lines
            for item in line.allocations
        ]
        return allocations_need_confirm(needs, stocks, allocs)

    async def _allocation_cells(
        self,
        sku_id: uuid.UUID,
        qty_by_location: dict[uuid.UUID, int],
    ) -> list:
        from app.schemas.pick import PickAllocationResponse

        stocks = {row.location_id: row for row in await self._stock_rows([sku_id])}
        cells = []
        for location_id, stock in stocks.items():
            if stock.is_archived:
                continue
            cells.append(
                PickAllocationResponse(
                    location_id=location_id,
                    location_name=stock.location_name,
                    qty=qty_by_location.get(location_id, 0),
                    on_hand=stock.on_hand,
                )
            )
        return cells

    async def _preview_lines(self, result: AllocationResult) -> list:
        from app.schemas.pick import PickLineResponse

        lines = []
        for line in result.lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            qty_by_location = {item.location_id: item.qty for item in line.allocations}
            lines.append(
                PickLineResponse(
                    sku_id=line.sku_id,
                    sku_our_ref=sku.our_ref,
                    sku_name=sku.name,
                    qty_needed=line.qty_needed,
                    qty_allocated=line.qty_allocated,
                    qty_short=line.qty_short,
                    allocations=await self._allocation_cells(line.sku_id, qty_by_location),
                )
            )
        return lines

    async def _get_or_404(self, pick_id: uuid.UUID) -> Pick:
        pick = await self.crud.get_by_id(pick_id)
        if pick is None:
            raise NotFoundError("Pick not found")
        return pick

    async def _to_response(self, pick: Pick) -> PickResponse:
        from app.schemas.pick import PickLineResponse

        needs_confirm = await self._needs_confirm(pick) if pick.lines else False
        lines = []
        for line in pick.lines:
            allocated = sum(item.qty for item in line.allocations)
            qty_by_location = {item.location_id: item.qty for item in line.allocations}
            lines.append(
                PickLineResponse(
                    sku_id=line.sku_id,
                    sku_our_ref=line.sku.our_ref,
                    sku_name=line.sku.name,
                    qty_needed=line.qty_needed,
                    qty_allocated=allocated,
                    qty_short=max(line.qty_needed - allocated, 0),
                    allocations=await self._allocation_cells(line.sku_id, qty_by_location),
                )
            )
        return PickResponse(
            id=pick.id,
            number=pick.number,
            source_type=pick.source_type,
            source_id=pick.source_id,
            kit_sku_id=pick.kit_sku_id,
            kit_sku_our_ref=pick.kit_sku.our_ref,
            kit_sku_name=pick.kit_sku.name,
            kit_qty=pick.kit_qty,
            status=pick.status,
            staging_location_id=pick.staging_location_id,
            customer_id=pick.customer_id,
            customer_name=pick.customer.name if pick.customer is not None else None,
            invoice_id=pick.invoice_id,
            needs_confirm=needs_confirm,
            lines=lines,
            created_at=pick.created_at,
            updated_at=pick.updated_at,
        )


class _PickOrigin:
    def __init__(
        self,
        source_type: PickSourceType,
        source_id: Optional[uuid.UUID],
        kit_sku_id: uuid.UUID,
        kit_qty: int,
        customer_id: Optional[uuid.UUID],
        invoice_id: Optional[uuid.UUID],
        needs: list[ComponentNeed],
    ) -> None:
        self.source_type = source_type
        self.source_id = source_id
        self.kit_sku_id = kit_sku_id
        self.kit_qty = kit_qty
        self.customer_id = customer_id
        self.invoice_id = invoice_id
        self.needs = needs
