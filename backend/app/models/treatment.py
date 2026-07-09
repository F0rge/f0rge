from __future__ import annotations

import datetime

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    group_name: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # Why the treatment was ended. Null = legacy "ended, unspecified" or still
    # active. Allowed values mirrored in schemas.treatment.TREATMENT_END_REASONS
    # and a DB CHECK constraint (see migration 015).
    end_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    end_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dose: Mapped[str | None] = mapped_column(String, nullable=True)
    # Null = not dose-tracked (e.g. "Low FODMAP diet"). 1..12 when set.
    doses_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    logs: Mapped[list[TreatmentLog]] = relationship(
        "TreatmentLog",
        back_populates="treatment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
