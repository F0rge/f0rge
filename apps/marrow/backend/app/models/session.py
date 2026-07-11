from __future__ import annotations

import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(nullable=False)
