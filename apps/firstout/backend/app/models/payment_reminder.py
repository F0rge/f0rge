from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PaymentReminderSend(UUIDPkMixin, TimestampMixin, Base):
    """One row per invoice and schedule step. Sent and skipped never send again."""

    __tablename__ = "payment_reminder_sends"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    offset_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    comms_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comms_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount_owing: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "invoice_id",
            "offset_days",
            name="uq_payment_reminder_sends_invoice_offset",
        ),
    )
