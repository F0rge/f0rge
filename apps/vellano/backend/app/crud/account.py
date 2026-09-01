from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal import JournalLine
from f0rge_db.crud import BaseCRUD


class AccountCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, account_id: uuid.UUID) -> Optional[Account]:
        return (
            await self.db.execute(select(Account).where(Account.id == account_id))
        ).scalar_one_or_none()

    async def get_by_code(self, code: str) -> Optional[Account]:
        return (
            await self.db.execute(select(Account).where(Account.code == code))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Account]:
        result = await self.db.execute(select(Account).order_by(Account.code))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Account))
        return int(result.scalar_one())

    async def get_balances(self) -> dict[uuid.UUID, Decimal]:
        result = await self.db.execute(
            select(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit_zar), 0)
                - func.coalesce(func.sum(JournalLine.credit_zar), 0),
            ).group_by(JournalLine.account_id)
        )
        return {row[0]: Decimal(row[1]) for row in result.all()}
