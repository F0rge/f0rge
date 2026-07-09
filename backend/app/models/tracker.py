from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class Tracker(Base):
    __tablename__ = "tracker"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_tracker_user_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.datetime.utcnow
    )

    logs: Mapped[list[TrackerLog]] = relationship(
        "TrackerLog",
        back_populates="tracker",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
