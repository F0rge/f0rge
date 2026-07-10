from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.supplement_catalog import SupplementCatalogItem

COPY_REFERENCE_CATALOGS_SQL = sa.text(
    "SELECT copy_user_catalog_from_reference(:new_user_id, :ref_user_id)"
)


class UserProvisioningCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def count_supplement_catalog_items(self) -> int:
        stmt = select(func.count()).select_from(SupplementCatalogItem)
        return (await self.db.execute(stmt)).scalar_one()

    async def bulk_insert_ignore_conflict(
        self,
        model: type,
        values: list[dict[str, object]],
        constraint_name: str,
    ) -> None:
        if not values:
            return
        stmt = insert(model).values(values).on_conflict_do_nothing(constraint=constraint_name)
        await self.db.execute(stmt)

    async def copy_reference_catalogs(self, new_user_id: uuid.UUID, ref_user_id: uuid.UUID) -> None:
        await self.db.execute(
            COPY_REFERENCE_CATALOGS_SQL,
            {"new_user_id": str(new_user_id), "ref_user_id": str(ref_user_id)},
        )
