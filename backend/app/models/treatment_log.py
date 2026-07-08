from __future__ import annotations

import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TreatmentLog(Base):
    __tablename__ = "treatment_log"

    treatment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("treatments.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    doses_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    __table_args__ = (PrimaryKeyConstraint("treatment_id", "date", name="pk_treatment_log"),)

    treatment: Mapped[Treatment] = relationship(
        "Treatment",
        back_populates="logs",
        lazy="selectin",
    )
