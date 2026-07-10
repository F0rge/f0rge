from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import default_user_id


class LabMarkerAlias(Base):
    __tablename__ = "lab_marker_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "alias", name="uq_lab_marker_aliases_user_id_alias"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=default_user_id,
    )
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("lab_marker_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String, nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)

    catalog: Mapped[LabMarkerCatalog] = relationship(
        "LabMarkerCatalog", back_populates="aliases", lazy="selectin"
    )
