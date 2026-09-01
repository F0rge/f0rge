from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import LocationStock, SkuStock
from app.models.purchase_order import PurchaseOrder, PurchaseOrderStatus
from app.models.team_settings import DEFAULT_HOME_CURRENCY
from app.schemas.home import HomeSummaryResponse
from app.services.packing_sheet import convert_bill_to_zar


class HomeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def summary(self) -> HomeSummaryResponse:
        on_order_qty = await self._sum_on_order_qty()
        on_hand_qty, on_hand_value = await self._sum_on_hand()
        on_order_value = await self._sum_on_order_value()

        return HomeSummaryResponse(
            on_order_qty=on_order_qty,
            on_order_value_zar=on_order_value.quantize(Decimal("0.01")),
            on_hand_qty=on_hand_qty,
            on_hand_value_zar=on_hand_value.quantize(Decimal("0.01")),
            home_currency=DEFAULT_HOME_CURRENCY,
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
                PurchaseOrder.status.in_(
                    [PurchaseOrderStatus.ON_WATER, PurchaseOrderStatus.LANDED]
                )
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
