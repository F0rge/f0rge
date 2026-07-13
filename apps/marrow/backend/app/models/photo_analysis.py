from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class PhotoAnalysis(Base):
    __tablename__ = "photo_analyses"
    __table_args__ = (
        Index("ix_photo_analyses_user_id", "user_id"),
        Index("ix_photo_analyses_meal_id", "meal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    meal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meals.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    photo_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("photos.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    dish_name: Mapped[str | None] = mapped_column(String, nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String, nullable=True)
    dish_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Per-meal user overrides: "this dish was actually gluten-free / lactose-free",
    # suppressing the corresponding scoring contribution (gluten flag / lactose FODMAP).
    gluten_free_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    lactose_free_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    meal: Mapped[Meal] = relationship("Meal", back_populates="analysis", lazy="selectin")
    photo: Mapped[Photo | None] = relationship("Photo", lazy="selectin")
    ingredients: Mapped[list[PhotoIngredient]] = relationship(
        "PhotoIngredient",
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
