from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payment import Payment
from f0rge_db.crud import BaseCRUD


class PaymentCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, payment_id: uuid.UUID) -> Optional[Payment]:
        return (
            await self.db.execute(
                select(Payment)
                .options(
                    selectinload(Payment.invoice),
                    selectinload(Payment.bill),
                )
                .where(Payment.id == payment_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Payment]:
        result = await self.db.execute(
            select(Payment)
            .options(
                selectinload(Payment.invoice),
                selectinload(Payment.bill),
            )
            .order_by(Payment.payment_number)
        )
        return list(result.scalars().all())

    async def get_next_payment_number(self) -> str:
        result = await self.db.execute(
            select(Payment.payment_number).order_by(Payment.payment_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "PAY-0001"
        num = int(last.split("-")[1]) + 1
        return f"PAY-{num:04d}"
