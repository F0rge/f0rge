from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DietTagCatalogItem(Base):
    __tablename__ = "diet_tag_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
