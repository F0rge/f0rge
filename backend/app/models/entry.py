from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    bloating: Mapped[int] = mapped_column(Integer, nullable=False)
    stool_normal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    joint_pain: Mapped[int] = mapped_column(Integer, nullable=False)
    neuro: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    stress: Mapped[int] = mapped_column(Integer, nullable=False)
    diet_risk: Mapped[str] = mapped_column(String, nullable=False)
    supplements: Mapped[str] = mapped_column(String, nullable=False)
    sick: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    photos: Mapped[list[Photo]] = relationship(
        "Photo", back_populates="entry", cascade="all, delete-orphan"
    )
