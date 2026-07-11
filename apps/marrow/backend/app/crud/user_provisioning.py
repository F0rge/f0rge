from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.dietary_ingredient import DietaryIngredient
from app.models.user import User

COPY_REFERENCE_CATALOGS_SQL = sa.text(
    "SELECT copy_user_catalog_from_reference(:new_user_id, :ref_user_id)"
)


class UserProvisioningCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def is_infrastructure_provisioned(self, user_id: uuid.UUID) -> bool:
        stmt = select(User.infrastructure_provisioned_at).where(User.id == user_id)
        provisioned_at = (await self.db.execute(stmt)).scalar_one_or_none()
        return provisioned_at is not None

    async def mark_infrastructure_provisioned(self, user_id: uuid.UUID) -> None:
        now = datetime.datetime.utcnow()
        await self.db.execute(
            update(User).where(User.id == user_id).values(infrastructure_provisioned_at=now)
        )

    async def count_dietary_ingredients(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DietaryIngredient)
            .where(DietaryIngredient.user_id == user_id)
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def bulk_insert_ignore_conflict(
        self,
        model: type,
        values: list[dict[str, object]],
        constraint_name: str,
    ) -> int:
        if not values:
            return 0
        stmt = insert(model).values(values).on_conflict_do_nothing(constraint=constraint_name)
        result = await self.db.execute(stmt)
        return result.rowcount or 0

    async def copy_reference_catalogs(self, new_user_id: uuid.UUID, ref_user_id: uuid.UUID) -> None:
        await self.db.execute(
            COPY_REFERENCE_CATALOGS_SQL,
            {"new_user_id": str(new_user_id), "ref_user_id": str(ref_user_id)},
        )
