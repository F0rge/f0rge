from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class BooksPeriodStatus(str, enum.Enum):
    OPEN = "open"
    LOCKED = "locked"


class BooksPeriod(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "books_periods"

    period_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_to: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[BooksPeriodStatus] = mapped_column(
        Enum(
            BooksPeriodStatus,
            name="books_period_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=BooksPeriodStatus.OPEN,
        server_default="open",
    )
    locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    locked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reopen_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "period_from",
            "period_to",
            name="uq_books_periods_period_from_period_to",
        ),
        CheckConstraint(
            "status IN ('open', 'locked')",
            name="ck_books_periods_status",
        ),
        CheckConstraint(
            "period_from <= period_to",
            name="ck_books_periods_period_range",
        ),
    )
