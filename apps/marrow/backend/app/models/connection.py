from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("user_low < user_high", name="ck_connections_order"),
        CheckConstraint("status IN ('pending', 'accepted')", name="ck_connections_status"),
        CheckConstraint("requester_id IN (user_low, user_high)", name="ck_connections_party"),
        UniqueConstraint("user_low", "user_high", name="uq_connections_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_low: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_high: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("(now() at time zone 'utc')")
    )
    responded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
