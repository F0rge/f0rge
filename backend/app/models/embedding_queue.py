from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class EmbeddingQueue(Base):
    """Durable outbox for the embedding pipeline worker.

    Rows are inserted by the enqueue_embedding() Postgres trigger on INSERT/UPDATE/DELETE
    of source tables (entries, labs, treatments, photo_analyses). The worker process
    claims rows with SKIP LOCKED, processes them, and deletes them on success.

    This ORM mapping exists so that Base.metadata.create_all() creates the table in
    test environments where migrations do not run.
    """

    __tablename__ = "embedding_queue"
    __table_args__ = (
        CheckConstraint(
            "action IN ('INSERT', 'UPDATE', 'DELETE')",
            name="embedding_queue_action_check",
        ),
        Index("ix_embedding_queue_user_id", "user_id"),
        # Partial index: only rows that still have attempts remaining need fast lookup.
        Index(
            "ix_embedding_queue_enqueued",
            "enqueued_at",
            postgresql_where=text("attempts < 5"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        default=default_user_id,
    )
    source_table: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    enqueued_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
