from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.ingredient_alias import IngredientAlias
from app.models.user import default_user_id


class DietaryIngredient(Base):
    __tablename__ = "dietary_ingredients"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "canonical_name",
            name="uq_dietary_ingredients_user_id_canonical_name",
        ),
        Index("ix_dietary_ingredients_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
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
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    aliases: Mapped[list[IngredientAlias]] = relationship(
        "IngredientAlias",
        cascade="all, delete-orphan",
        back_populates="ingredient",
        lazy="selectin",
    )
