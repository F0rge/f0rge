"""Everything the SKU side panel and full view read, in one call."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location_bin import BinStockCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku_stock_figures import (
    arriving_orders,
    held_documents_by_sku_id,
    on_order_by_sku_id,
)
from app.models.location import Location
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.unit_cost_audit import UnitCostAudit, UnitCostAuditSource
from app.permissions import STOCK_COST_VIEW
from app.schemas.inventory import LocationStockResponse
from app.schemas.location_bin import BinOnHandResponse
from app.schemas.sku_overview import (
    SkuActivityEntry,
    SkuHeldDocument,
    SkuKitUse,
    SkuNextArrival,
    SkuOverviewResponse,
    SkuOverviewStock,
)
from app.services.permissions import PermissionService
from app.services.sku_supplier_prices import SkuSupplierPriceService
from app.services.skus import SkuService
from app.services.stock_availability import StockAvailability
from app.services.packing_sheet import sku_level_unit_cost
from f0rge_db.organisation import tenant_id_ctx

ACTIVITY_LIMIT = 15
SOURCE_LABELS = {
    UnitCostAuditSource.LAND: "Landed",
    UnitCostAuditSource.RECEIVE: "Received",
    UnitCostAuditSource.CORRECTION: "Cost correction",
    UnitCostAuditSource.OPENING: "Opening stock",
    UnitCostAuditSource.STOCKTAKE: "Stocktake",
    UnitCostAuditSource.ADJUSTMENT: "Stock adjustment",
    UnitCostAuditSource.IMPORT: "CSV import",
    UnitCostAuditSource.RETURN: "Return",
    UnitCostAuditSource.LAYBY: "Layby",
    UnitCostAuditSource.SALES_ORDER: "Sales order",
    UnitCostAuditSource.STOREFRONT: "Shop order",
    UnitCostAuditSource.TILL_PICK: "Till pick",
    UnitCostAuditSource.TILL: "Till sale",
}


class SkuOverviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.skus = SkuService(db)

    async def get(self, sku_id: uuid.UUID, user_id: uuid.UUID) -> SkuOverviewResponse:
        sku_response = await self.skus.get(sku_id, user_id)  # 404 for another tenant too
        sku = await self.skus.crud.get_by_id(sku_id)
        assert sku is not None
        sees_cost = await PermissionService(self.db).has_permission(user_id, STOCK_COST_VIEW)
        return SkuOverviewResponse(
            sku=sku_response,
            stock=await self._stock(sku, sees_cost),
            supplier_prices=await SkuSupplierPriceService(self.db).rows_for(
                sku, sees_cost=sees_cost
            ),
            is_kit=sku_response.is_kit,
            used_in_kits=await self._used_in_kits(sku.id),
            activity=await self._activity(sku.id, sees_cost),
        )

    async def _stock(self, sku: Sku, sees_cost: bool) -> SkuOverviewStock:
        location_stocks = sorted(
            await LocationStockCRUD(self.db).list_by_sku_id(sku.id),
            key=lambda row: row.location.name,
        )
        bins: dict[uuid.UUID, list[BinOnHandResponse]] = {}
        for row in sorted(
            await BinStockCRUD(self.db).list_nonzero_for_skus([sku.id]),
            key=lambda row: row.bin.code,
        ):
            bins.setdefault(row.bin.location_id, []).append(
                BinOnHandResponse(bin_id=row.bin_id, code=row.bin.code, on_hand=row.on_hand)
            )
        held = (await held_documents_by_sku_id(self.db, [sku.id])).get(sku.id, [])
        now = datetime.datetime.now(datetime.timezone.utc)
        available = (await StockAvailability(self.db).company_available([sku.id], now))[sku.id]
        unit_cost = sku_level_unit_cost([(ls.on_hand, ls.unit_cost_zar) for ls in location_stocks])
        return SkuOverviewStock(
            on_hand=sum((ls.on_hand for ls in location_stocks), Decimal(0)),
            held=sum((doc.qty for doc in held), Decimal(0)),
            held_documents=[
                SkuHeldDocument(kind=doc.kind, id=doc.id, number=doc.number, qty=doc.qty)
                for doc in held
            ],
            # Shown never below zero, like the till.
            available=max(Decimal(0), available),
            on_order=(await on_order_by_sku_id(self.db, [sku.id])).get(sku.id, Decimal(0)),
            next_arrival=await self._next_arrival(sku),
            unit_cost_zar=unit_cost if sees_cost else None,
            locations=[
                LocationStockResponse(
                    location_id=ls.location_id,
                    location_name=ls.location.name,
                    on_hand=ls.on_hand,
                    unit_cost_zar=ls.unit_cost_zar if sees_cost else None,
                    bins=bins.get(ls.location_id, []),
                )
                for ls in location_stocks
            ],
        )

    async def _next_arrival(self, sku: Sku) -> Optional[SkuNextArrival]:
        orders = await arriving_orders(self.db, sku.id)
        if not orders:
            return None
        first = orders[0]
        expected: Optional[datetime.date] = None
        # A planned date only before the goods ship; once on water or landed no ETA is stored.
        if first.status == "open" and first.ordered_at is not None and sku.lead_time_days:
            expected = first.ordered_at.date() + datetime.timedelta(days=sku.lead_time_days)
        return SkuNextArrival(
            purchase_order_id=first.id,
            po_number=first.po_number,
            status=first.status,
            qty=first.qty,
            expected_on=expected,
            expected_on_basis="planned_lead_time" if expected is not None else None,
        )

    async def _used_in_kits(self, sku_id: uuid.UUID) -> list[SkuKitUse]:
        rows = await self.db.execute(
            select(SkuBomLine.parent_sku_id, Sku.our_ref, Sku.name, SkuBomLine.qty, Sku.is_archived)
            .join(Sku, Sku.id == SkuBomLine.parent_sku_id)
            .where(SkuBomLine.team_id == tenant_id_ctx.get(), SkuBomLine.component_sku_id == sku_id)
            .order_by(Sku.our_ref)
        )
        return [
            SkuKitUse(parent_sku_id=pid, our_ref=ref, name=name, qty=qty, parent_is_archived=arch)
            for pid, ref, name, qty, arch in rows
        ]

    async def _activity(self, sku_id: uuid.UUID, sees_cost: bool) -> list[SkuActivityEntry]:
        rows = await self.db.execute(
            select(UnitCostAudit, Location.name)
            .outerjoin(Location, Location.id == UnitCostAudit.location_id)
            .where(UnitCostAudit.team_id == tenant_id_ctx.get(), UnitCostAudit.sku_id == sku_id)
            .order_by(UnitCostAudit.created_at.desc(), UnitCostAudit.id.desc())
            .limit(ACTIVITY_LIMIT)
        )
        return [
            SkuActivityEntry(
                id=audit.id,
                source=audit.source.value,
                source_label=SOURCE_LABELS.get(audit.source, audit.source.value),
                location_id=audit.location_id,
                location_name=location_name,
                created_at=audit.created_at,
                note=audit.note,
                old_cost_zar=audit.old_cost_zar if sees_cost else None,
                new_cost_zar=audit.new_cost_zar if sees_cost else None,
            )
            for audit, location_name in rows
        ]
