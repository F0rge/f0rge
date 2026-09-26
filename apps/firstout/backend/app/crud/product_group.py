from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku


class ProductGroupCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_groups(self) -> list[ProductGroup]:
        return list(
            (await self.db.execute(select(ProductGroup).order_by(ProductGroup.title))).scalars()
        )

    async def get_group(self, group_id: uuid.UUID) -> Optional[ProductGroup]:
        return (
            await self.db.execute(select(ProductGroup).where(ProductGroup.id == group_id))
        ).scalar_one_or_none()

    async def add_group(self, title: str, options: dict[str, list[str]]) -> ProductGroup:
        group = ProductGroup(title=title, options=options)
        self.db.add(group)
        await self.db.flush()
        return group

    async def variants(self, group_id: uuid.UUID) -> list[tuple[ProductGroupVariant, Sku]]:
        rows = await self.db.execute(
            select(ProductGroupVariant, Sku)
            .join(Sku, Sku.id == ProductGroupVariant.source_sku_id)
            .where(ProductGroupVariant.product_group_id == group_id)
            .order_by(Sku.our_ref)
        )
        return list(rows.all())

    async def mapped_sku_ids(
        self, sku_ids: list[uuid.UUID], exclude_group_id: Optional[uuid.UUID]
    ) -> set[uuid.UUID]:
        if not sku_ids:
            return set()
        query = select(ProductGroupVariant.source_sku_id).where(
            ProductGroupVariant.source_sku_id.in_(sku_ids)
        )
        if exclude_group_id is not None:
            query = query.where(ProductGroupVariant.product_group_id != exclude_group_id)
        return set((await self.db.execute(query)).scalars())

    async def skus(self, sku_ids: list[uuid.UUID]) -> dict[uuid.UUID, Sku]:
        if not sku_ids:
            return {}
        return {
            sku.id: sku
            for sku in (await self.db.execute(select(Sku).where(Sku.id.in_(sku_ids)))).scalars()
        }

    async def replace_variants(
        self,
        group_id: uuid.UUID,
        assignments: list[tuple[uuid.UUID, dict[str, str], str]],
    ) -> None:
        await self.db.execute(
            delete(ProductGroupVariant).where(ProductGroupVariant.product_group_id == group_id)
        )
        for sku_id, options, signature in assignments:
            self.db.add(
                ProductGroupVariant(
                    product_group_id=group_id,
                    source_sku_id=sku_id,
                    options=options,
                    option_signature=signature,
                )
            )
        await self.db.flush()
