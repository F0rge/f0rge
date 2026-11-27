from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class SkuSupplierPrice(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    """Cin7 product price by supplier. Not a landed cost and not a PO line."""

    __tablename__ = "sku_supplier_prices"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    fixed_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    # The least this supplier accepts, and the increment it ships in.
    min_order_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pack_multiple: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("sku_id", "supplier_id", name="uq_sku_supplier_prices_sku_supplier"),
        CheckConstraint("min_order_qty >= 1", name="ck_sku_supplier_prices_min_order_qty"),
        CheckConstraint("pack_multiple >= 1", name="ck_sku_supplier_prices_pack_multiple"),
    )
