from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import uuid
from typing import Optional

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.inventory import LocationStock
from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku
from app.models.team import Team


@dataclass(frozen=True)
class PublishedSkuSnapshot:
    id: uuid.UUID
    sku: str
    name: str
    retail_ex_vat: Decimal
    available_quantity: int
    revision: datetime
    observed_at: datetime
    product_group_id: Optional[uuid.UUID]
    product_title: Optional[str]
    options: dict[str, str]


class OpsCommerceCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_company(self, company_id: uuid.UUID) -> bool:
        return (
            await self.db.execute(select(Team.id).where(Team.id == company_id))
        ).scalar_one_or_none() is not None

    async def published_products(self) -> list[PublishedSkuSnapshot]:
        member = aliased(Sku)
        mapped = aliased(ProductGroupVariant)
        incomplete_group = exists(
            select(mapped.id)
            .join(member, member.id == mapped.source_sku_id)
            .where(
                mapped.product_group_id == ProductGroup.id,
                (
                    member.storefront_published.is_(False)
                    | (member.retail_ex_vat <= 0)
                    | member.retail_ex_vat.is_(None)
                ),
            )
        )
        result = await self.db.execute(
            select(
                Sku.id,
                Sku.our_ref,
                Sku.name,
                Sku.retail_ex_vat,
                func.coalesce(func.sum(LocationStock.on_hand), 0),
                func.greatest(
                    Sku.updated_at,
                    func.coalesce(func.max(LocationStock.updated_at), Sku.updated_at),
                    func.coalesce(ProductGroup.updated_at, Sku.updated_at),
                    func.coalesce(ProductGroupVariant.updated_at, Sku.updated_at),
                ),
                func.clock_timestamp(),
                ProductGroup.id,
                ProductGroup.title,
                ProductGroupVariant.options,
            )
            .outerjoin(LocationStock, LocationStock.sku_id == Sku.id)
            .outerjoin(ProductGroupVariant, ProductGroupVariant.source_sku_id == Sku.id)
            .outerjoin(ProductGroup, ProductGroup.id == ProductGroupVariant.product_group_id)
            .where(
                Sku.storefront_published.is_(True),
                Sku.retail_ex_vat > 0,
                (
                    ProductGroupVariant.id.is_(None)
                    | (ProductGroup.storefront_published.is_(True) & ~incomplete_group)
                ),
            )
            .group_by(Sku.id, ProductGroup.id, ProductGroupVariant.id)
            .order_by(Sku.our_ref)
        )
        return [
            PublishedSkuSnapshot(
                id=row[0],
                sku=row[1],
                name=row[2],
                retail_ex_vat=row[3],
                available_quantity=max(0, row[4]),
                revision=row[5],
                observed_at=row[6],
                product_group_id=row[7],
                product_title=row[8],
                options=row[9] or {},
            )
            for row in result.all()
        ]
