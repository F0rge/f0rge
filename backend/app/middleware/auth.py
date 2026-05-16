from __future__ import annotations

import datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import AuthSession
from app.services.auth import get_session_by_token


async def get_current_session(
    ht_session: str = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthSession:
    if not ht_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = await get_session_by_token(db, ht_session)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    if session.expires_at < datetime.datetime.utcnow():
        await db.delete(session)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    return session
