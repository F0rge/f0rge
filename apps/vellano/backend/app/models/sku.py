from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Sku(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "skus"

    our_ref: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    our_barcode: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    design: Mapped[str] = mapped_column(String(255), nullable=False)
    fabric: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    preferred_supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    photo_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    wholesale_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    retail_ex_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    __table_args__ = (
        Index(
            "ix_skus_design_fabric_lower",
            text("lower(design)"),
            text("lower(fabric)"),
            unique=True,
        ),
    )
