from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bank_import import BankImportLine
from app.models.inventory import LocationStock, SkuStock
from app.models.layby import Layby, LaybyStatus
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.sku import Sku
from app.models.stock_return import StockReturn, StockReturnStatus
from app.models.stocktake import Stocktake, StocktakeStatus
from app.models.team_settings import DEFAULT_HOME_CURRENCY
from app.models.unit_cost_audit import UnitCostAudit
from app.schemas.home import HomeAttentionItem, HomeRecentMovement, HomeSummaryResponse
from app.services.packing_sheet import convert_bill_to_zar

AGED_STOCK_DAYS = 180
LOW_STOCK_MIN = 1
LOW_STOCK_MAX = 2
MAX_ATTENTION_ITEMS = 8
MAX_RECENT_MOVEMENTS = 10


class HomeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def summary(self) -> HomeSummaryResponse:
        on_order_qty = await self._sum_on_order_qty()
        on_hand_qty, on_hand_value = await self._sum_on_hand()
        on_order_value = await self._sum_on_order_value()
        aged_stock_value = await self._sum_aged_stock_value()
        open_laybys_count, open_laybys_balance = await self._open_laybys_totals()
        low_stock_count = await self._count_low_stock_skus()
        open_returns_count = await self._count_draft_returns()
        unmatched_bank_count = await self._count_unmatched_bank_lines()
        overdue_laybys_count = await self._count_overdue_laybys()

        needs_attention = self._build_needs_attention(
            low_stock_rows=await self._low_stock_sku_rows(limit=3),
            stocktake_rows=await self._in_progress_stocktake_rows(limit=2),
            open_returns_count=open_returns_count,
            overdue_laybys_count=overdue_laybys_count,
            unmatched_bank_count=unmatched_bank_count,
        )
        recent_movements = await self._recent_movements()

        return HomeSummaryResponse(
            on_order_qty=on_order_qty,
            on_order_value_zar=on_order_value.quantize(Decimal("0.01")),
            on_hand_qty=on_hand_qty,
            on_hand_value_zar=on_hand_value.quantize(Decimal("0.01")),
            home_currency=DEFAULT_HOME_CURRENCY,
            aged_stock_value_zar=aged_stock_value.quantize(Decimal("0.01")),
            open_laybys_count=open_laybys_count,
            open_laybys_balance_zar=open_laybys_balance.quantize(Decimal("0.01")),
            low_stock_count=low_stock_count,
            open_returns_count=open_returns_count,
            needs_attention=needs_attention,
            recent_movements=recent_movements,
        )

    async def _sum_on_order_qty(self) -> int:
        result = await self.db.execute(select(func.coalesce(func.sum(SkuStock.on_order), 0)))
        return int(result.scalar_one())

    async def _sum_on_hand(self) -> tuple[int, Decimal]:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(LocationStock.on_hand), 0),
                func.coalesce(
                    func.sum(LocationStock.on_hand * LocationStock.unit_cost_zar),
                    0,
                ),
            ).where(LocationStock.on_hand > 0)
        )
        row = result.one()
        qty = int(row[0])
        value = Decimal(str(row[1])) if row[1] is not None else Decimal("0")
        return qty, value

    async def _sum_on_order_value(self) -> Decimal:
        result = await self.db.execute(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.lines),
                selectinload(PurchaseOrder.supplier),
            )
            .where(
                PurchaseOrder.status.in_([PurchaseOrderStatus.ON_WATER, PurchaseOrderStatus.LANDED])
            )
        )
        orders = list(result.scalars().all())
        total = Decimal("0")
        for po in orders:
            fx = po.fx_to_zar if po.fx_to_zar is not None and po.fx_to_zar > 0 else Decimal("1")
            factory_cur = po.supplier.default_currency or "USD"
            for line in po.lines:
                if line.unit_cost_zar is not None:
                    total += Decimal(line.qty) * line.unit_cost_zar
                else:
                    line_factory_zar = convert_bill_to_zar(
                        line.factory_unit_amount,
                        factory_cur,
                        fx,
                    )
                    total += Decimal(line.qty) * line_factory_zar
        return total

    async def _sum_aged_stock_value(self) -> Decimal:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=AGED_STOCK_DAYS)
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(LocationStock.on_hand * LocationStock.unit_cost_zar),
                    0,
                )
            ).where(
                LocationStock.on_hand > 0,
                LocationStock.updated_at <= cutoff,
            )
        )
        value = result.scalar_one()
        return Decimal(str(value)) if value is not None else Decimal("0")

    async def _open_laybys_totals(self) -> tuple[int, Decimal]:
        result = await self.db.execute(
            select(
                func.count(Layby.id),
                func.coalesce(func.sum(Layby.total_inc_vat - Layby.amount_paid), 0),
            ).where(Layby.status.in_([LaybyStatus.OPEN, LaybyStatus.READY]))
        )
        row = result.one()
        count = int(row[0])
        balance = Decimal(str(row[1])) if row[1] is not None else Decimal("0")
        return count, balance

    async def _count_low_stock_skus(self) -> int:
        totals = self._sku_on_hand_totals_subquery()
        result = await self.db.execute(
            select(func.count())
            .select_from(totals)
            .where(totals.c.total_on_hand >= LOW_STOCK_MIN)
            .where(totals.c.total_on_hand <= LOW_STOCK_MAX)
        )
        return int(result.scalar_one())

    async def _low_stock_sku_rows(self, limit: int) -> list[tuple[str, str, int]]:
        totals = self._sku_on_hand_totals_subquery()
        result = await self.db.execute(
            select(Sku.name, Sku.our_ref, totals.c.total_on_hand)
            .join(totals, Sku.id == totals.c.sku_id)
            .where(totals.c.total_on_hand >= LOW_STOCK_MIN)
            .where(totals.c.total_on_hand <= LOW_STOCK_MAX)
            .order_by(totals.c.total_on_hand, Sku.our_ref)
            .limit(limit)
        )
        return [(row[0], row[1], int(row[2])) for row in result.all()]

    def _sku_on_hand_totals_subquery(self):
        return (
            select(
                LocationStock.sku_id,
                func.sum(LocationStock.on_hand).label("total_on_hand"),
            )
            .group_by(LocationStock.sku_id)
            .subquery()
        )

    async def _count_draft_returns(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(StockReturn)
            .where(StockReturn.status == StockReturnStatus.DRAFT)
        )
        return int(result.scalar_one())

    async def _count_overdue_laybys(self) -> int:
        today = datetime.date.today()
        result = await self.db.execute(
            select(func.count())
            .select_from(Layby)
            .where(
                Layby.status == LaybyStatus.OPEN,
                Layby.due_date < today,
            )
        )
        return int(result.scalar_one())

    async def _count_unmatched_bank_lines(self) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(BankImportLine)
            .where(BankImportLine.matched_payment_id.is_(None))
        )
        return int(result.scalar_one())

    async def _in_progress_stocktake_rows(self, limit: int) -> list[str]:
        result = await self.db.execute(
            select(Stocktake)
            .options(selectinload(Stocktake.location))
            .where(Stocktake.status == StocktakeStatus.IN_PROGRESS)
            .order_by(Stocktake.started_at.desc())
            .limit(limit)
        )
        stocktakes = list(result.scalars().all())
        return [stocktake.location.name for stocktake in stocktakes]

    async def _recent_movements(self) -> list[HomeRecentMovement]:
        result = await self.db.execute(
            select(UnitCostAudit)
            .options(
                selectinload(UnitCostAudit.sku),
                selectinload(UnitCostAudit.location),
            )
            .order_by(UnitCostAudit.created_at.desc())
            .limit(MAX_RECENT_MOVEMENTS)
        )
        rows = list(result.scalars().all())
        return [self._movement_from_audit(row) for row in rows]

    @staticmethod
    def _movement_from_audit(row: UnitCostAudit) -> HomeRecentMovement:
        title = row.sku.our_ref if row.sku is not None else (row.note or "")
        location_name = row.location.name if row.location is not None else None
        source = row.source.value
        detail = f"{source} — {location_name}" if location_name else source
        return HomeRecentMovement(
            source=source,
            title=title,
            detail=detail,
            created_at=row.created_at,
        )

    @staticmethod
    def _build_needs_attention(
        low_stock_rows: list[tuple[str, str, int]],
        stocktake_rows: list[str],
        open_returns_count: int,
        overdue_laybys_count: int,
        unmatched_bank_count: int,
    ) -> list[HomeAttentionItem]:
        items: list[HomeAttentionItem] = []

        for name, our_ref, on_hand in low_stock_rows:
            items.append(
                HomeAttentionItem(
                    kind="low_stock",
                    title=name,
                    detail=our_ref,
                    status=f"{on_hand} on hand",
                    href="/catalogue",
                )
            )

        for location_name in stocktake_rows:
            items.append(
                HomeAttentionItem(
                    kind="stocktake",
                    title=f"Stocktake — {location_name}",
                    detail="",
                    status="In progress",
                    href="/stocktakes",
                )
            )

        if open_returns_count > 0:
            items.append(
                HomeAttentionItem(
                    kind="returns",
                    title="Returns pending inspection",
                    detail="",
                    status=f"{open_returns_count} pending",
                    href="/returns",
                )
            )

        if overdue_laybys_count > 0:
            items.append(
                HomeAttentionItem(
                    kind="layby",
                    title="Overdue laybys",
                    detail="",
                    status=f"{overdue_laybys_count} overdue",
                    href="/laybys",
                )
            )

        if unmatched_bank_count > 0:
            items.append(
                HomeAttentionItem(
                    kind="bank",
                    title="Unmatched bank lines",
                    detail="",
                    status=f"{unmatched_bank_count} lines",
                    href="/bank-reconciliation",
                )
            )

        return items[:MAX_ATTENTION_ITEMS]
