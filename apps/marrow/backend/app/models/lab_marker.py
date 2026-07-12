from __future__ import annotations

import uuid

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class LabMarker(Base):
    __tablename__ = "lab_markers"
    __table_args__ = (
        Index("ix_lab_markers_canonical_lab", "canonical_name", "lab_id"),
        Index("ix_lab_markers_user_id", "user_id"),
        Index("ix_lab_markers_lab_id", "lab_id"),
        Index("ix_lab_markers_canonical_name", "canonical_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
    )
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("lab_marker_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    ref_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_text: Mapped[str | None] = mapped_column(String, nullable=True)
    flag: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    lab: Mapped[Lab] = relationship("Lab", back_populates="markers", lazy="selectin")
    catalog: Mapped[LabMarkerCatalog] = relationship("LabMarkerCatalog", lazy="selectin")
