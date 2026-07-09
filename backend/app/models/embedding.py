from __future__ import annotations

import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import default_user_id


class Embedding(Base):
    __tablename__ = "embedding"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    source_table: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    # Source lookups (source_table, source_id) use the leading columns of the
    # composite unique index automatically — no separate ix_embedding_source needed.
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_table",
            "source_id",
            "chunk_index",
            "embedding_model",
            name="uq_embedding_user_source_chunk_model",
        ),
    )
