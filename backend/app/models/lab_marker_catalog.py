from __future__ import annotations

import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LabMarkerCatalog(Base):
    __tablename__ = "lab_marker_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    common_units: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow
    )

    aliases: Mapped[list[LabMarkerAlias]] = relationship(
        "LabMarkerAlias", cascade="all, delete-orphan", back_populates="catalog"
    )
