from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class LookbookPriceMode(str, enum.Enum):
    RETAIL = "retail"
    PRICE_LIST = "price_list"
    HIDDEN = "hidden"


class LookbookEventType(str, enum.Enum):
    OPEN = "open"
    SKU_VISIBLE = "sku_visible"
    SKU_OPEN = "sku_open"
    HEART = "heart"
    UNHEART = "unheart"
    SUBMIT = "submit"


class Lookbook(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "lookbooks"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    price_mode: Mapped[LookbookPriceMode] = mapped_column(
        Enum(
            LookbookPriceMode,
            name="lookbook_price_mode",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    price_list_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_lists.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped["User"] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    items: Mapped[list["LookbookItem"]] = relationship(
        back_populates="lookbook",
        cascade="all, delete-orphan",
        order_by="LookbookItem.position",
    )

    __table_args__ = (
        UniqueConstraint("token", name="uq_lookbooks_token"),
        CheckConstraint(
            "price_mode IN ('retail', 'price_list', 'hidden')",
            name="ck_lookbooks_price_mode",
        ),
        CheckConstraint(
            "(price_mode = 'price_list' AND price_list_id IS NOT NULL) OR "
            "(price_mode <> 'price_list' AND price_list_id IS NULL)",
            name="ck_lookbooks_price_list_id",
        ),
    )


class LookbookItem(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "lookbook_items"

    lookbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_name: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_our_ref: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_unit_inc_vat: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    snapshot_photo_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lookbook: Mapped[Lookbook] = relationship(back_populates="items")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (
        UniqueConstraint("lookbook_id", "sku_id", name="uq_lookbook_items_lookbook_sku"),
        UniqueConstraint("lookbook_id", "position", name="uq_lookbook_items_lookbook_position"),
        CheckConstraint("position >= 0", name="ck_lookbook_items_position"),
    )


from app.models.customer import Customer  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.user import User  # noqa: E402


class LookbookEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "lookbook_events"

    lookbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=True,
    )
    event_type: Mapped[LookbookEventType] = mapped_column(
        Enum(
            LookbookEventType,
            name="lookbook_event_type",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    visitor_id: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('open', 'sku_visible', 'sku_open', 'heart', 'unheart', 'submit')",
            name="ck_lookbook_events_type",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_lookbook_events_duration",
        ),
    )


class LookbookQuote(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "lookbook_quotes"

    lookbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("quote_id", name="uq_lookbook_quotes_quote_id"),)
