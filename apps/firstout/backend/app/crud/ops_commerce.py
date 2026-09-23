from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock
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


class OpsCommerceCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_company(self, company_id: uuid.UUID) -> bool:
        return (
            await self.db.execute(select(Team.id).where(Team.id == company_id))
        ).scalar_one_or_none() is not None

    async def published_products(self) -> list[PublishedSkuSnapshot]:
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
                ),
                func.clock_timestamp(),
            )
            .outerjoin(LocationStock, LocationStock.sku_id == Sku.id)
            .where(Sku.storefront_published.is_(True), Sku.retail_ex_vat > 0)
            .group_by(Sku.id)
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
            )
            for row in result.all()
        ]
