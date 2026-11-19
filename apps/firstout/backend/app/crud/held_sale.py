from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import any_, bindparam, delete, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.held_sale import HeldSale
from app.models.held_sale_operation import HeldSaleOperation
from app.models.location import Location, LocationType
from app.models.pick import Pick
from app.models.sku import Sku
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx


class HeldSaleCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def showroom(self, location_id: uuid.UUID, *, lock: bool = False) -> Optional[Location]:
        query = select(Location).where(
            Location.team_id == tenant_id_ctx.get(),
            Location.id == location_id,
            Location.type == LocationType.SHOWROOM,
        )
        if lock:
            # NO KEY UPDATE serializes held-sale mutations and location lifecycle
            # changes without blocking unrelated foreign-key references to the showroom.
            query = query.with_for_update(key_share=True).execution_options(populate_existing=True)
        return await self.db.scalar(query)

    @staticmethod
    def _scoped_sales(location_id: uuid.UUID):
        return select(HeldSale).where(
            HeldSale.team_id == tenant_id_ctx.get(), HeldSale.location_id == location_id
        )

    async def list(self, location_id: uuid.UUID) -> list[HeldSale]:
        query = self._scoped_sales(location_id).order_by(
            HeldSale.held_at.desc(), HeldSale.id.desc()
        )
        return list(await self.db.scalars(query))

    async def get(self, location_id: uuid.UUID, held_id: uuid.UUID) -> Optional[HeldSale]:
        return await self.db.scalar(self._scoped_sales(location_id).where(HeldSale.id == held_id))

    async def ids(self, location_id: uuid.UUID) -> set[uuid.UUID]:
        query = self._scoped_sales(location_id).with_only_columns(HeldSale.id)
        return set(await self.db.scalars(query))

    async def delete_sales(self, location_id: uuid.UUID, ids: set[uuid.UUID]) -> None:
        await self.db.execute(
            delete(HeldSale).where(
                HeldSale.team_id == tenant_id_ctx.get(),
                HeldSale.location_id == location_id,
                HeldSale.id
                == any_(bindparam("held_ids", list(ids), type_=ARRAY(UUID(as_uuid=True)))),
            )
        )

    async def operation(
        self,
        location_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        operation_id: uuid.UUID,
        now: datetime.datetime,
    ) -> Optional[HeldSaleOperation]:
        return await self.db.scalar(
            select(HeldSaleOperation).where(
                HeldSaleOperation.team_id == tenant_id_ctx.get(),
                HeldSaleOperation.location_id == location_id,
                HeldSaleOperation.actor_id == actor_id,
                HeldSaleOperation.action == action,
                HeldSaleOperation.operation_id == operation_id,
                HeldSaleOperation.expires_at > now,
            )
        )

    async def prune_operations(self, location_id: uuid.UUID, now: datetime.datetime) -> None:
        await self.db.execute(
            delete(HeldSaleOperation).where(
                HeldSaleOperation.team_id == tenant_id_ctx.get(),
                HeldSaleOperation.location_id == location_id,
                HeldSaleOperation.expires_at <= now,
            )
        )

    async def customer(self, customer_id: Optional[uuid.UUID]) -> Optional[Customer]:
        identity = (
            Customer.id == customer_id if customer_id else Customer.name == WALK_IN_CUSTOMER_NAME
        )
        return await self.db.scalar(
            select(Customer)
            .where(Customer.team_id == tenant_id_ctx.get(), identity)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )

    async def skus(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, Sku]:
        query = (
            select(Sku)
            .where(Sku.team_id == tenant_id_ctx.get(), Sku.id.in_(ids))
            .order_by(Sku.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return {sku.id: sku for sku in await self.db.scalars(query)}

    async def picks(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Pick]:
        if not ids:
            return {}
        query = (
            select(Pick)
            .where(Pick.team_id == tenant_id_ctx.get(), Pick.id.in_(ids))
            .order_by(Pick.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return {pick.id: pick for pick in await self.db.scalars(query)}
