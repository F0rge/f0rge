from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class TreatmentLog(Base):
    __tablename__ = "treatment_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
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

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "treatment_id", "date", name="pk_treatment_log"),
        Index("ix_treatment_log_user_id", "user_id"),
        Index("ix_treatment_log_date", "date"),
    )

    treatment: Mapped[Treatment] = relationship(
        "Treatment",
        back_populates="logs",
        lazy="selectin",
    )
