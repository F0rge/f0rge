from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.category_account_map import CategoryAccountMapCRUD
from app.models.category_account_map import CategoryAccountMap
from app.models.sku import Sku
from app.services.chart_of_accounts import CODE_COGS, CODE_SALES


class CategoryPostingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CategoryAccountMapCRUD(db)
        self._maps_by_lower: Optional[dict[str, CategoryAccountMap]] = None

    async def map_for_category(self, category: Optional[str]) -> Optional[CategoryAccountMap]:
        if category is None or not category.strip():
            return None
        maps = await self._maps()
        return maps.get(category.strip().lower())

    async def sales_code_for_sku(self, sku: Optional[Sku]) -> str:
        return await self._code_for_sku(sku, "sales_code", CODE_SALES)

    async def cogs_code_for_sku(self, sku: Optional[Sku]) -> str:
        return await self._code_for_sku(sku, "cogs_code", CODE_COGS)

    async def stock_adj_code_for_sku(self, sku: Optional[Sku]) -> str:
        return await self._code_for_sku(sku, "stock_adj_code", CODE_COGS)

    async def count_var_code_for_sku(self, sku: Optional[Sku]) -> str:
        return await self._code_for_sku(sku, "count_var_code", CODE_COGS)

    def collapse(
        self, lines: list[tuple[str, Decimal, Decimal]]
    ) -> list[tuple[str, Decimal, Decimal]]:
        nets: dict[str, Decimal] = {}
        order: list[str] = []
        for code, debit, credit in lines:
            if code not in nets:
                order.append(code)
                nets[code] = Decimal(0)
            nets[code] += debit - credit
        collapsed: list[tuple[str, Decimal, Decimal]] = []
        for code in order:
            net = nets[code]
            if net > 0:
                collapsed.append((code, net, Decimal(0)))
            elif net < 0:
                collapsed.append((code, Decimal(0), -net))
        return collapsed

    async def _code_for_sku(self, sku: Optional[Sku], attr: str, fallback: str) -> str:
        category = None if sku is None else sku.category
        mapping = await self.map_for_category(category)
        if mapping is None:
            return fallback
        return getattr(mapping, attr)

    async def _maps(self) -> dict[str, CategoryAccountMap]:
        if self._maps_by_lower is None:
            rows = await self.crud.list_all()
            self._maps_by_lower = {row.category.lower(): row for row in rows}
        return self._maps_by_lower
