from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class DeliverySourceType(str, enum.Enum):
    INVOICE = "invoice"
    LAYBY = "layby"


class DeliveryStatus(str, enum.Enum):
    DRAFT = "draft"
    PACKED = "packed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Delivery(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "deliveries"

    delivery_number: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[DeliverySourceType] = mapped_column(
        Enum(
            DeliverySourceType,
            name="delivery_source_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    layby_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("laybys.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            name="delivery_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    delivery_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    invoice: Mapped[Optional["TaxInvoice"]] = relationship()
    layby: Mapped[Optional["Layby"]] = relationship()
    location: Mapped["Location"] = relationship()
    created_by: Mapped["User"] = relationship()
    lines: Mapped[list["DeliveryLine"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        order_by="DeliveryLine.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("delivery_number", name="uq_deliveries_delivery_number"),
        CheckConstraint(
            "(source_type = 'invoice' AND invoice_id IS NOT NULL AND layby_id IS NULL) "
            "OR (source_type = 'layby' AND layby_id IS NOT NULL AND invoice_id IS NULL)",
            name="ck_deliveries_source",
        ),
        CheckConstraint(
            "status IN ('draft', 'packed', 'delivered', 'cancelled')",
            name="ck_deliveries_status",
        ),
        Index(
            "uq_deliveries_invoice_active",
            "invoice_id",
            unique=True,
            postgresql_where=text("invoice_id IS NOT NULL AND status != 'cancelled'"),
        ),
        Index(
            "uq_deliveries_layby_active",
            "layby_id",
            unique=True,
            postgresql_where=text("layby_id IS NOT NULL AND status != 'cancelled'"),
        ),
    )


class DeliveryLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "delivery_lines"

    delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    delivery: Mapped[Delivery] = relationship(back_populates="lines")
    sku: Mapped[Optional["Sku"]] = relationship()

    __table_args__ = (CheckConstraint("qty > 0", name="ck_delivery_lines_qty"),)


from app.models.layby import Layby  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
from app.models.user import User  # noqa: E402
