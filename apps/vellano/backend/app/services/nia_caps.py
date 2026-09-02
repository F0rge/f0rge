from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def check_nia_budget(db: AsyncSession, user_id: uuid.UUID) -> None:
    """No-op until N5 implements per-user token caps."""
    return
