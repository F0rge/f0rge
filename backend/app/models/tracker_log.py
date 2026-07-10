from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class TrackerLog(Base):
    __tablename__ = "tracker_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    tracker_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    __table_args__ = (PrimaryKeyConstraint("user_id", "tracker_id", "date", name="pk_tracker_log"),)

    tracker: Mapped[Tracker] = relationship(
        "Tracker",
        back_populates="logs",
        lazy="selectin",
    )
