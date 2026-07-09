from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class LabMarkerCatalog(Base):
    __tablename__ = "lab_marker_catalog"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "canonical_name",
            name="uq_lab_marker_catalog_user_id_canonical_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    common_units: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    aliases: Mapped[list[LabMarkerAlias]] = relationship(
        "LabMarkerAlias",
        cascade="all, delete-orphan",
        back_populates="catalog",
        lazy="selectin",
    )
