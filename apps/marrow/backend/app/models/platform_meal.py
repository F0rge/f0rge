from __future__ import annotations

import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlatformMeal(Base):
    """Curated meal template available to all users from the platform library."""

    __tablename__ = "platform_meals"
    __table_args__ = (
        Index("ix_platform_meals_slug", "slug", unique=True),
        Index("ix_platform_meals_cuisine", "cuisine"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    cuisine: Mapped[str] = mapped_column(String, nullable=False)
    icon_key: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        default=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    ingredients: Mapped[list[PlatformMealIngredient]] = relationship(
        "PlatformMealIngredient",
        back_populates="meal",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PlatformMealIngredient.sort_order",
    )


class PlatformMealIngredient(Base):
    __tablename__ = "platform_meal_ingredients"
    __table_args__ = (Index("ix_platform_meal_ingredients_meal_id", "platform_meal_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_meal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("platform_meals.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    meal: Mapped[PlatformMeal] = relationship(
        "PlatformMeal",
        back_populates="ingredients",
        lazy="selectin",
    )
