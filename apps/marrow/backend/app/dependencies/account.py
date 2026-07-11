from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.account import AccountService


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)
