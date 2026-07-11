from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class PhotoIngredient(Base):
    __tablename__ = "photo_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("photo_analyses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str | None] = mapped_column(String, nullable=True)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    histamine_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fodmap_oligos: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_fructose: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_polyols: Mapped[str | None] = mapped_column(String, nullable=True)
    fodmap_lactose: Mapped[str | None] = mapped_column(String, nullable=True)
    contains_gluten: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    contains_dairy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )

    analysis: Mapped[PhotoAnalysis] = relationship(
        "PhotoAnalysis", back_populates="ingredients", lazy="selectin"
    )
