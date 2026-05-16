from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabMarker(Base):
    __tablename__ = "lab_markers"
    __table_args__ = (
        Index("ix_lab_markers_canonical_lab", "canonical_name", "lab_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("lab_marker_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    ref_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    ref_text: Mapped[str | None] = mapped_column(String, nullable=True)
    flag: Mapped[str] = mapped_column(String, nullable=False)

    lab: Mapped[Lab] = relationship("Lab", back_populates="markers", lazy="selectin")
    catalog: Mapped[LabMarkerCatalog] = relationship(
        "LabMarkerCatalog", lazy="selectin"
    )
