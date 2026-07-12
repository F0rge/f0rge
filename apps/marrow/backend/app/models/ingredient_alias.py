from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id

if TYPE_CHECKING:
    from app.models.dietary_ingredient import DietaryIngredient


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "alias", name="uq_ingredient_aliases_user_id_alias"),
        ForeignKeyConstraint(
            ["user_id", "canonical_name"],
            ["dietary_ingredients.user_id", "dietary_ingredients.canonical_name"],
        ),
        Index("ix_ingredient_aliases_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    alias: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, default="en")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    ingredient: Mapped["DietaryIngredient"] = relationship(
        "DietaryIngredient", back_populates="aliases", lazy="selectin"
    )
