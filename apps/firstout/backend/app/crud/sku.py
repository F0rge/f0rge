from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku import Sku
from f0rge_db.crud import BaseCRUD


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SkuCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, sku_id: uuid.UUID) -> Optional[Sku]:
        return (await self.db.execute(select(Sku).where(Sku.id == sku_id))).scalar_one_or_none()

    async def list_all(self, category: Optional[str] = None, q: Optional[str] = None) -> list[Sku]:
        rows, _total = await self.list_filtered(category=category, q=q, limit=None)
        return rows

    async def list_filtered(
        self,
        *,
        category: Optional[str] = None,
        q: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> tuple[list[Sku], int]:
        filters = self._filters(category, q)
        count_stmt = select(func.count()).select_from(Sku)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(await self.db.scalar(count_stmt) or 0)
        stmt = select(Sku)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(Sku.our_ref, Sku.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_categories(self) -> list[str]:
        result = await self.db.execute(
            select(Sku.category).where(Sku.category.is_not(None)).distinct()
        )
        values: set[str] = set()
        for category in result.scalars().all():
            if category is None:
                continue
            cleaned = category.strip()
            if cleaned:
                values.add(cleaned)
        return sorted(values, key=str.casefold)

    def _filters(self, category: Optional[str], q: Optional[str]) -> list:
        filters = []
        if category is not None:
            filters.append(func.lower(Sku.category) == category.lower())
        if q:
            pattern = f"%{_escape_like(q)}%"
            filters.append(
                or_(
                    Sku.name.ilike(pattern, escape="\\"),
                    Sku.our_ref.ilike(pattern, escape="\\"),
                    Sku.our_barcode.ilike(pattern, escape="\\"),
                )
            )
        return filters

    async def get_by_design_fabric_insensitive(
        self,
        design: str,
        fabric: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[Sku]:
        stmt = select(Sku).where(
            func.lower(Sku.design) == design.lower(),
            func.lower(Sku.fabric) == fabric.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(Sku.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_our_ref(
        self,
        our_ref: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[Sku]:
        stmt = select(Sku).where(Sku.our_ref == our_ref)
        if exclude_id is not None:
            stmt = stmt.where(Sku.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_our_barcode(
        self,
        our_barcode: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[Sku]:
        stmt = select(Sku).where(Sku.our_barcode == our_barcode)
        if exclude_id is not None:
            stmt = stmt.where(Sku.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
