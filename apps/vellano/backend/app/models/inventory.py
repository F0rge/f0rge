from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class SkuStock(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sku_stock"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    on_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sku: Mapped["Sku"] = relationship()


class LocationStock(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "location_stock"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)

    sku: Mapped["Sku"] = relationship()
    location: Mapped["Location"] = relationship()

    __table_args__ = (
        UniqueConstraint("sku_id", "location_id", name="uq_location_stock_sku_location"),
    )


from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
