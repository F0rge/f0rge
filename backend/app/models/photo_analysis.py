from __future__ import annotations

import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PhotoAnalysis(Base):
    __tablename__ = "photo_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photos.id"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    dish_name: Mapped[str | None] = mapped_column(String, nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String, nullable=True)
    dish_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    photo: Mapped[Photo] = relationship("Photo", back_populates="analysis")
    ingredients: Mapped[list[PhotoIngredient]] = relationship(
        "PhotoIngredient", back_populates="analysis", cascade="all, delete-orphan"
    )
