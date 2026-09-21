from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import UUIDPkMixin


class BooksDocumentType(str, enum.Enum):
    INVOICE = "invoice"
    BILL = "bill"
    PAYMENT = "payment"
    JOURNAL = "journal"


class BooksEventAction(str, enum.Enum):
    CREATED = "created"
    POSTED = "posted"
    VOIDED = "voided"


class BooksEvent(UUIDPkMixin, Base):
    __tablename__ = "books_events"

    document_type: Mapped[BooksDocumentType] = mapped_column(
        Enum(
            BooksDocumentType,
            name="books_document_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    action: Mapped[BooksEventAction] = mapped_column(
        Enum(
            BooksEventAction,
            name="books_event_action",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('invoice', 'bill', 'payment', 'journal')",
            name="ck_books_events_document_type",
        ),
        CheckConstraint(
            "action IN ('created', 'posted', 'voided')",
            name="ck_books_events_action",
        ),
    )
