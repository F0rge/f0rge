from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dietary_ingredient import DietaryIngredient


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str] = mapped_column(
        String, ForeignKey("dietary_ingredients.canonical_name"), nullable=False
    )
    language: Mapped[str] = mapped_column(String, default="en")

    ingredient: Mapped["DietaryIngredient"] = relationship(
        "DietaryIngredient", back_populates="aliases", lazy="selectin"
    )
