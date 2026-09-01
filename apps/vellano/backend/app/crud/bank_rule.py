from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_rule import BankRule
from f0rge_db.crud import BaseCRUD


class BankRuleCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, rule_id: uuid.UUID) -> Optional[BankRule]:
        return (
            await self.db.execute(select(BankRule).where(BankRule.id == rule_id))
        ).scalar_one_or_none()

    async def list_all(self, bank_account_id: Optional[uuid.UUID] = None) -> list[BankRule]:
        stmt = select(BankRule).order_by(BankRule.created_at, BankRule.id)
        if bank_account_id is not None:
            stmt = stmt.where(BankRule.bank_account_id == bank_account_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_account(self, bank_account_id: uuid.UUID) -> list[BankRule]:
        result = await self.db.execute(
            select(BankRule)
            .where(
                BankRule.bank_account_id == bank_account_id,
                BankRule.is_active.is_(True),
            )
            .order_by(BankRule.created_at, BankRule.id)
        )
        return list(result.scalars().all())

    async def get_by_account_pattern(
        self,
        bank_account_id: uuid.UUID,
        pattern: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[BankRule]:
        stmt = select(BankRule).where(
            BankRule.bank_account_id == bank_account_id,
            BankRule.pattern == pattern,
        )
        if exclude_id is not None:
            stmt = stmt.where(BankRule.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
