from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from f0rge_db.mixins import TimestampMixin


class ClerkWebhookEvent(TimestampMixin, Base):
    """Durable replay protection; never retain identity payloads or credentials."""

    __tablename__ = "clerk_webhook_events"
    svix_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
