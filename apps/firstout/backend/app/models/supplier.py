from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Supplier(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    vat_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    __table_args__ = (
        Index("ix_suppliers_team_id_is_archived", "team_id", "is_archived"),
        Index(
            "ix_suppliers_name_lower",
            text("lower(name)"),
            unique=True,
        ),
        Index("ix_suppliers_vat_number", "vat_number"),
    )
