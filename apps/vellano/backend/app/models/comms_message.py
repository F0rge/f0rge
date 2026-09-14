from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import UUIDPkMixin


class CommsChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class CommsProvider(str, enum.Enum):
    SMTP = "smtp"
    WHATSAPP_CLICK = "whatsapp_click"
    WHATSAPP_CLOUD = "whatsapp_cloud"


class CommsDocumentType(str, enum.Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    LAYBY = "layby"


class CommsStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    OPENED = "opened"


class CommsMessage(UUIDPkMixin, Base):
    __tablename__ = "comms_messages"

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    channel: Mapped[CommsChannel] = mapped_column(
        Enum(
            CommsChannel,
            name="comms_channel",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    provider: Mapped[CommsProvider] = mapped_column(
        Enum(
            CommsProvider,
            name="comms_provider",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    document_type: Mapped[CommsDocumentType] = mapped_column(
        Enum(
            CommsDocumentType,
            name="comms_document_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_identity: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[CommsStatus] = mapped_column(
        Enum(
            CommsStatus,
            name="comms_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=CommsStatus.PENDING,
    )
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "channel IN ('email', 'whatsapp')",
            name="ck_comms_messages_channel",
        ),
        CheckConstraint(
            "provider IN ('smtp', 'whatsapp_click', 'whatsapp_cloud')",
            name="ck_comms_messages_provider",
        ),
        CheckConstraint(
            "document_type IN ('invoice', 'credit_note', 'layby')",
            name="ck_comms_messages_document_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'opened')",
            name="ck_comms_messages_status",
        ),
        Index("ix_comms_messages_document", "document_type", "document_id"),
        Index("ix_comms_messages_created_at", "created_at"),
    )
