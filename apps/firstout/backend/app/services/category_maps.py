from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.category_account_map import CategoryAccountMapCRUD
from app.models.category_account_map import CategoryAccountMap
from app.schemas.category_account_map import CategoryAccountMapResponse, CategoryAccountMapUpsert
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work


class CategoryMapService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CategoryAccountMapCRUD(db)
        self.account_crud = AccountCRUD(db)

    async def list(self) -> list[CategoryAccountMapResponse]:
        return [self._to_response(row) for row in await self.crud.list_all()]

    async def upsert(self, data: CategoryAccountMapUpsert) -> CategoryAccountMapResponse:
        await self._assert_codes_exist(data)
        existing = await self.crud.get_by_category_insensitive(data.category)
        async with unit_of_work(self.db):
            if existing is None:
                row = CategoryAccountMap(
                    category=data.category,
                    sales_code=data.sales_code,
                    cogs_code=data.cogs_code,
                    stock_adj_code=data.stock_adj_code,
                    count_var_code=data.count_var_code,
                )
                await self.crud.add_and_flush(row)
            else:
                existing.category = data.category
                existing.sales_code = data.sales_code
                existing.cogs_code = data.cogs_code
                existing.stock_adj_code = data.stock_adj_code
                existing.count_var_code = data.count_var_code
                row = existing
                await self.crud.flush()

        reloaded = await self.crud.get_by_id(row.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def _assert_codes_exist(self, data: CategoryAccountMapUpsert) -> None:
        for code in (
            data.sales_code,
            data.cogs_code,
            data.stock_adj_code,
            data.count_var_code,
        ):
            account = await self.account_crud.get_by_code(code)
            if account is None:
                raise NotFoundError(f"Account {code} not found")

    @staticmethod
    def _to_response(row: CategoryAccountMap) -> CategoryAccountMapResponse:
        return CategoryAccountMapResponse(
            id=row.id,
            category=row.category,
            sales_code=row.sales_code,
            cogs_code=row.cogs_code,
            stock_adj_code=row.stock_adj_code,
            count_var_code=row.count_var_code,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
