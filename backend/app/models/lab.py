from __future__ import annotations

import datetime

from sqlalchemy import Date, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    lab_location: Mapped[str | None] = mapped_column(String, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    attachment_path: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String, nullable=False, default="confirmed"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    markers: Mapped[list[LabMarker]] = relationship(
        "LabMarker", cascade="all, delete-orphan", back_populates="lab", lazy="selectin"
    )
