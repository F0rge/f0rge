from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class PriceList(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "price_lists"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    items: Mapped[list[PriceListItem]] = relationship(
        "PriceListItem",
        back_populates="price_list",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_price_lists_team_id_is_archived", "team_id", "is_archived"),)


class PriceListItem(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "price_list_items"

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    price_list: Mapped[PriceList] = relationship(
        "PriceList",
        back_populates="items",
        lazy="selectin",
    )
    sku: Mapped["Sku"] = relationship("Sku", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("price_list_id", "sku_id", name="uq_price_list_items_list_sku"),
        CheckConstraint("unit_ex_vat > 0", name="ck_price_list_items_unit_ex_vat_positive"),
    )
