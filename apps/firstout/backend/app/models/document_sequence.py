from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

DEFAULT_DOCUMENT_PADDING = 4


class DocumentSequence(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "document_sequences"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_DOCUMENT_PADDING)
    next_value: Mapped[int] = mapped_column(BigInteger, nullable=False)

    team: Mapped["Team"] = relationship()

    __table_args__ = (
        UniqueConstraint("team_id", "doc_type", name="uq_document_sequences_team_doc_type"),
    )


from app.models.team import Team  # noqa: E402
