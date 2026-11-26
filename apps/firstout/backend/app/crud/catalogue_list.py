"""Persistence for the managed catalogue lists. Tenant scope comes from RLS."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import func, select, union, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.catalogue_list import Material, SkuCategory, SkuMaterial
from app.models.category_account_map import CategoryAccountMap
from app.models.sku import Sku
from f0rge_db.crud import BaseCRUD


class SkuCategoryCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, category_id: uuid.UUID) -> Optional[SkuCategory]:
        return (
            await self.db.execute(
                select(SkuCategory)
                .where(SkuCategory.id == category_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[SkuCategory]:
        return list((await self.db.execute(select(SkuCategory))).scalars().all())

    async def active_names(
        self, parent_id: Optional[uuid.UUID], exclude_id: Optional[uuid.UUID] = None
    ) -> list[str]:
        """Names of the active categories on one level: top-level, or one parent's children."""
        stmt = select(SkuCategory.name).where(SkuCategory.is_archived.is_(False))
        stmt = stmt.where(
            SkuCategory.parent_id.is_(None)
            if parent_id is None
            else SkuCategory.parent_id == parent_id
        )
        if exclude_id is not None:
            stmt = stmt.where(SkuCategory.id != exclude_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def active_sku_counts(self) -> dict[uuid.UUID, int]:
        """Active SKUs per category id and per sub-category id (the ids never collide)."""
        counts: dict[uuid.UUID, int] = {}
        for column in (Sku.category_id, Sku.subcategory_id):
            rows = await self.db.execute(
                select(column, func.count())
                .where(column.is_not(None), Sku.is_archived.is_(False))
                .group_by(column)
            )
            counts.update({key: int(count) for key, count in rows.all()})
        return counts

    async def active_sku_count(self, category: SkuCategory) -> int:
        column = Sku.category_id if category.parent_id is None else Sku.subcategory_id
        return int(
            await self.db.scalar(
                select(func.count())
                .select_from(Sku)
                .where(column == category.id, Sku.is_archived.is_(False))
            )
            or 0
        )

    async def archive_active_children(self, parent_id: uuid.UUID, at: datetime.datetime) -> None:
        await self.db.execute(
            update(SkuCategory)
            .where(SkuCategory.parent_id == parent_id, SkuCategory.is_archived.is_(False))
            .values(is_archived=True, archived_at=at)
            .execution_options(synchronize_session="fetch")
        )

    async def sales_accounts_by_category(self) -> dict[str, tuple[str, str]]:
        """lower(category name) -> (sales account code, account name), as posting looks it up."""
        rows = await self.db.execute(
            select(CategoryAccountMap.category, Account.code, Account.name).join(
                Account, Account.code == CategoryAccountMap.sales_code
            )
        )
        return {category.lower(): (code, name) for category, code, name in rows.all()}

    async def rename_sku_read_model(self, category_id: uuid.UUID, name: str) -> None:
        # Keep updated_at: the shop feed does not carry the category name, so a rename
        # must not make every SKU in the category look changed to the storefront sync.
        await self.db.execute(
            update(Sku)
            .where(Sku.category_id == category_id)
            .values(category=name, updated_at=Sku.updated_at)
            .execution_options(synchronize_session="fetch")
        )

    async def touch_skus(self, category_id: uuid.UUID, at: datetime.datetime) -> None:
        """Bump SKUs whose shop section changed, so the shop feed revision moves."""
        await self.db.execute(
            update(Sku)
            .where(Sku.category_id == category_id)
            .values(updated_at=at)
            .execution_options(synchronize_session="fetch")
        )


class MaterialCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, material_id: uuid.UUID) -> Optional[Material]:
        return (
            await self.db.execute(
                select(Material)
                .where(Material.id == material_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Material]:
        return list((await self.db.execute(select(Material))).scalars().all())

    async def active_names(self, exclude_id: Optional[uuid.UUID] = None) -> list[str]:
        stmt = select(Material.name).where(Material.is_archived.is_(False))
        if exclude_id is not None:
            stmt = stmt.where(Material.id != exclude_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def active_sku_counts(self) -> dict[uuid.UUID, int]:
        """Distinct active SKUs per material, as main or other material."""
        uses = union(
            select(Sku.main_material_id.label("material_id"), Sku.id.label("sku_id")).where(
                Sku.main_material_id.is_not(None), Sku.is_archived.is_(False)
            ),
            select(SkuMaterial.material_id, SkuMaterial.sku_id)
            .join(Sku, Sku.id == SkuMaterial.sku_id)
            .where(Sku.is_archived.is_(False)),
        ).subquery()
        rows = await self.db.execute(
            select(uses.c.material_id, func.count()).group_by(uses.c.material_id)
        )
        return {key: int(count) for key, count in rows.all()}
