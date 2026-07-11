from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.auth import AuthService


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)
