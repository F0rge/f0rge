"""Reversible catalogue lifecycle, with a reviewed snapshot of its dependencies."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.delivery import Delivery, DeliveryLine
from app.models.inventory import LocationStock, SkuStock
from app.models.layby import Layby, LaybyLine
from app.models.location import Location
from app.models.location_bin import BinStock
from app.models.pick import Pick, PickLine
from app.models.purchase_order import PoLine, PurchaseOrder
from app.models.quote import Quote, QuoteLine
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.sku import Sku
from app.models.sku_bom_line import SkuBomLine
from app.models.stock_adjustment import StockAdjustment, StockAdjustmentLine
from app.models.stock_return import StockReturn, StockReturnLine
from app.models.stocktake import Stocktake, StocktakeLine
from app.models.team import Team
from app.models.transfer import Transfer, TransferLine
from app.schemas.quantity import quantity_text
from app.services.record_workspace_filters import payload_hash
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx


@dataclass
class SkuArchiveImpact:
    reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    dependencies: list[dict] = field(default_factory=list)
    fingerprint: str = ""


class SkuArchiveService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def lock_skus(self, ids: list[uuid.UUID]) -> None:
        """Shared lock order for lifecycle, BOM changes and new business validation.

        The tenant row serializes graph edits, including insertion of a previously
        absent dependency. Locking existing BOM rows alone cannot protect that gap.
        """
        team_id = tenant_id_ctx.get()
        if team_id is None:
            raise NotFoundError("Organisation not found")
        await self.db.execute(select(Team.id).where(Team.id == team_id).with_for_update())
        if ids:
            refreshed = await self.db.scalars(
                select(Sku)
                .where(Sku.team_id == team_id, Sku.id.in_(ids))
                .order_by(Sku.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            refreshed.all()

    async def graph(self, sku_id: uuid.UUID):
        team_id = tenant_id_ctx.get()
        skus = {
            sku.id: sku
            for sku in (
                await self.db.scalars(
                    select(Sku)
                    .where(Sku.team_id == team_id)
                    .execution_options(populate_existing=True)
                )
            ).all()
        }
        if sku_id not in skus:
            raise NotFoundError("SKU not found")
        edges = list(
            (await self.db.scalars(select(SkuBomLine).where(SkuBomLine.team_id == team_id))).all()
        )
        connected = {sku_id}
        while True:
            adjacent = {
                endpoint
                for edge in edges
                if edge.parent_sku_id in connected or edge.component_sku_id in connected
                for endpoint in (edge.parent_sku_id, edge.component_sku_id)
            }
            if adjacent <= connected:
                break
            connected |= adjacent
        relevant = [edge for edge in edges if edge.parent_sku_id in connected]
        return skus, relevant, connected

    @staticmethod
    def graph_problem(skus, edges) -> Optional[str]:
        parents = {edge.parent_sku_id for edge in edges}
        for edge in edges:
            if (
                edge.parent_sku_id not in skus
                or edge.component_sku_id not in skus
                or not Decimal(edge.qty).is_finite()
                or edge.qty <= 0
                or edge.parent_sku_id == edge.component_sku_id
            ):
                return "The kit recipe needs correction before changing archive status"
            if edge.component_sku_id in parents:
                return "Nested or cyclic kits need correction before changing archive status"
        return None

    async def impact(self, sku_id: uuid.UUID, action: str) -> SkuArchiveImpact:
        skus, edges, connected = await self.graph(sku_id)
        sku = skus[sku_id]
        impact = SkuArchiveImpact(reason=self.graph_problem(skus, edges))
        parents = [
            skus[edge.parent_sku_id]
            for edge in edges
            if edge.component_sku_id == sku_id and edge.parent_sku_id in skus
        ]
        components = [
            skus[edge.component_sku_id]
            for edge in edges
            if edge.parent_sku_id == sku_id and edge.component_sku_id in skus
        ]
        if impact.reason is None and action == "archive":
            active_parents = [parent for parent in parents if not parent.is_archived]
            if active_parents:
                impact.reason = "This component is used by active kits. Replace it in those recipes or archive the kits first"
                impact.dependencies = [
                    {"id": parent.id, "label": f"{parent.our_ref} · {parent.name}"}
                    for parent in sorted(active_parents, key=lambda item: item.our_ref)
                ]
            # With auto-publish on, the flag no longer controls the shop: an archived SKU
            # leaves the feed and commerce withdraws it.
            elif (
                sku.storefront_published and not settings.ops_commerce_auto_publish_enabled
            ) or self.active_mto(sku):
                impact.reason = "Withdraw this SKU from the online shop and end its active made-to-order offer before archiving"
        elif impact.reason is None and action == "restore":
            inactive = [component for component in components if component.is_archived]
            if inactive:
                impact.reason = "Restore the archived components before restoring this kit"
                impact.dependencies = [
                    {"id": component.id, "label": f"{component.our_ref} · {component.name}"}
                    for component in sorted(inactive, key=lambda item: item.our_ref)
                ]
        stock, stock_warnings = await self._stock_snapshot(sku_id)
        documents, document_warnings = await self._document_snapshot(sku_id)
        if action == "archive":
            impact.warnings = stock_warnings + document_warnings
        impact.fingerprint = payload_hash(
            {
                "graph_nodes": [
                    (
                        str(key),
                        skus[key].is_archived,
                        str(skus[key].updated_at),
                        skus[key].storefront_published,
                        self.active_mto(skus[key]),
                    )
                    for key in sorted(
                        {sku_id}
                        | {edge.parent_sku_id for edge in edges if edge.component_sku_id == sku_id}
                        | {edge.component_sku_id for edge in edges if edge.parent_sku_id == sku_id},
                        key=str,
                    )
                    if key in skus
                ],
                "graph_edges": sorted(
                    (
                        str(edge.id),
                        str(edge.parent_sku_id),
                        str(edge.component_sku_id),
                        quantity_text(edge.qty),
                    )
                    for edge in edges
                ),
                "stock": stock,
                "documents": documents,
            }
        )
        return impact

    @staticmethod
    def active_mto(sku: Sku) -> bool:
        expiry = sku.made_to_order_expires_at
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=datetime.timezone.utc)
        return bool(
            sku.made_to_order_offer_id
            and sku.made_to_order_capacity is not None
            and sku.made_to_order_capacity > 0
            and expiry is not None
            and expiry > datetime.datetime.now(datetime.timezone.utc)
        )

    async def set_archived(self, sku_id: uuid.UUID, archived: bool, actor: uuid.UUID) -> None:
        await self.lock_skus([sku_id])
        impact = await self.impact(sku_id, "archive" if archived else "restore")
        if impact.reason:
            raise ConflictError(impact.reason)
        sku = await self.db.scalar(
            select(Sku).where(Sku.id == sku_id, Sku.team_id == tenant_id_ctx.get())
        )
        async with unit_of_work(self.db):
            sku.is_archived = archived
            sku.archived_at = datetime.datetime.utcnow() if archived else None
            sku.archived_by_id = actor if archived else None

    async def _stock_snapshot(self, sku_id: uuid.UUID):
        team_id = tenant_id_ctx.get()
        locations = (
            await self.db.execute(
                select(LocationStock.id, Location.name, LocationStock.on_hand)
                .join(Location, Location.id == LocationStock.location_id)
                .where(LocationStock.team_id == team_id, LocationStock.sku_id == sku_id)
                .order_by(LocationStock.id)
            )
        ).all()
        bins = (
            await self.db.execute(
                select(BinStock.id, BinStock.bin_id, BinStock.on_hand)
                .where(BinStock.team_id == team_id, BinStock.sku_id == sku_id)
                .order_by(BinStock.id)
            )
        ).all()
        on_order = (
            await self.db.execute(
                select(SkuStock.id, SkuStock.on_order)
                .where(SkuStock.team_id == team_id, SkuStock.sku_id == sku_id)
                .order_by(SkuStock.id)
            )
        ).all()
        warnings = [
            f"Recorded stock: {quantity_text(qty)} at {name}. This stays in Stock and reports; archiving does not write it off."
            for _, name, qty in locations
            if qty != 0
        ]
        warnings.extend(
            f"Recorded on-order quantity: {quantity_text(qty)}. Existing receipts remain possible."
            for _, qty in on_order
            if qty != 0
        )
        return {
            "locations": [(str(key), name, quantity_text(qty)) for key, name, qty in locations],
            "bins": [(str(key), str(bin_id), quantity_text(qty)) for key, bin_id, qty in bins],
            "on_order": [(str(key), quantity_text(qty)) for key, qty in on_order],
        }, warnings

    async def _document_snapshot(self, sku_id: uuid.UUID):
        snapshots, warnings = {}, []
        # Existing operational documents keep their SKU. Archive history is not an open commitment.
        definitions = [
            ("quotes", Quote, QuoteLine, "quote_id", {"draft", "sent"}),
            (
                "sales orders",
                SalesOrder,
                SalesOrderLine,
                "sales_order_id",
                {"draft", "open", "awaiting_stock"},
            ),
            ("laybys", Layby, LaybyLine, "layby_id", {"open", "ready"}),
            (
                "purchase orders",
                PurchaseOrder,
                PoLine,
                "po_id",
                {"pending_approval", "open", "on_water", "landed"},
            ),
            ("transfers", Transfer, TransferLine, "transfer_id", {"draft", "in_transit"}),
            ("deliveries", Delivery, DeliveryLine, "delivery_id", {"draft", "packed", "loaded"}),
            ("stocktakes", Stocktake, StocktakeLine, "stocktake_id", {"in_progress"}),
            ("adjustments", StockAdjustment, StockAdjustmentLine, "adjustment_id", {"draft"}),
            ("returns", StockReturn, StockReturnLine, "return_id", {"draft"}),
            ("picks", Pick, PickLine, "pick_id", {"draft", "confirmed", "picking", "staged"}),
        ]
        for title, document, line, foreign_key, states in definitions:
            # Some operational line models intentionally have no timestamps.
            conditions = [document.team_id == tenant_id_ctx.get(), document.status.in_(states)]
            if hasattr(document, "is_archive"):
                conditions.append(document.is_archive.is_(False))
            conditions.append(
                or_(line.sku_id == sku_id, Pick.kit_sku_id == sku_id)
                if document is Pick
                else line.sku_id == sku_id
            )
            rows = (
                await self.db.execute(
                    select(
                        document.id, document.status, document.updated_at, *line.__table__.columns
                    )
                    .join(line, getattr(line, foreign_key) == document.id)
                    .where(*conditions)
                    .order_by(document.id, line.id)
                )
            ).all()
            snapshots[title] = [
                [str(getattr(value, "value", value)) for value in row] for row in rows
            ]
            count = len({row[0] for row in rows})
            if count:
                warnings.append(
                    f"{count} open {title}: existing quantities can still be completed or cancelled; new quantities require restoring the SKU."
                )
        return snapshots, warnings
