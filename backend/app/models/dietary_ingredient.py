from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DietaryIngredient(Base):
    __tablename__ = "dietary_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    histamine_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fodmap_oligos: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_fructose: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_polyols: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_lactose: Mapped[str | None] = mapped_column(String, nullable=True)
    contains_gluten: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_dairy: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
