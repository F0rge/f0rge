from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabMarkerAlias(Base):
    __tablename__ = "lab_marker_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("lab_marker_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    language: Mapped[str | None] = mapped_column(String, nullable=True)

    catalog: Mapped[LabMarkerCatalog] = relationship(
        "LabMarkerCatalog", back_populates="aliases", lazy="selectin"
    )
