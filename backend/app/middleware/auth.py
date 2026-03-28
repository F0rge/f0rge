from __future__ import annotations

import datetime

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.session import AuthSession


def get_current_session(
    ht_session: str = Cookie(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not ht_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = (
        db.query(AuthSession).filter(AuthSession.token == ht_session).first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    if session.expires_at < datetime.datetime.utcnow():
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    return session
