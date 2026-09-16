from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin

CHANNEL_SLUG_SHOPIFY = "shopify"
CHANNEL_SLUG_EMAIL = "email"
CHANNEL_SLUG_MANUAL = "manual"


class ChannelAtpMode(str, enum.Enum):
    WAREHOUSE_ONLY = "warehouse_only"
    POOLED = "pooled"
    MAPPED = "mapped"


class ChannelOrderStatus(str, enum.Enum):
    RECEIVED = "received"
    POSTED = "posted"
    NEEDS_MAPPING = "needs_mapping"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ChannelOutboxKind(str, enum.Enum):
    INVENTORY_PUSH = "inventory_push"
    FULFILLMENT_PUSH = "fulfillment_push"
    PROCESS_ORDER = "process_order"


class ChannelOutboxStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class SalesChannel(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sales_channels"

    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shopify_shop_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shopify_admin_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shopify_webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    maps: Mapped[list["ChannelLocationMap"]] = relationship(back_populates="channel")
    listings: Mapped[list["ChannelListing"]] = relationship(back_populates="channel")

    __table_args__ = (UniqueConstraint("slug", name="uq_sales_channels_slug"),)


class ChannelLocationMap(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "channel_location_maps"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shopify_location_gid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    include_in_atp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    channel: Mapped[SalesChannel] = relationship(back_populates="maps")
    location: Mapped["Location"] = relationship()

    __table_args__ = (
        UniqueConstraint("channel_id", "location_id", name="uq_channel_location_maps_pair"),
    )


class ChannelListing(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "channel_listings"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_variant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    external_inventory_item_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    external_sku: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    channel: Mapped[SalesChannel] = relationship(back_populates="listings")
    sku: Mapped["Sku"] = relationship()

    __table_args__ = (
        UniqueConstraint("channel_id", "sku_id", name="uq_channel_listings_sku"),
        Index(
            "uq_channel_listings_variant",
            "channel_id",
            "external_variant_id",
            unique=True,
            postgresql_where=text("external_variant_id IS NOT NULL"),
        ),
    )


class ChannelApiKey(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "channel_api_keys"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)

    created_by: Mapped["User"] = relationship()

    __table_args__ = (UniqueConstraint("key_hash", name="uq_channel_api_keys_hash"),)


class ChannelOrder(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "channel_orders"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sales_channels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ChannelOrderStatus] = mapped_column(
        Enum(
            ChannelOrderStatus,
            name="channel_order_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    pick_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("picks.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliveries.id", ondelete="SET NULL"),
        nullable=True,
    )
    shopify_fulfillment_order_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    allocations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    channel: Mapped[SalesChannel] = relationship()
    customer: Mapped[Optional["Customer"]] = relationship()
    invoice: Mapped[Optional["TaxInvoice"]] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "channel_id",
            "external_order_id",
            name="uq_channel_orders_external",
        ),
    )


class ChannelOutbox(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "channel_outbox"

    kind: Mapped[ChannelOutboxKind] = mapped_column(
        Enum(
            ChannelOutboxKind,
            name="channel_outbox_kind",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    status: Mapped[ChannelOutboxStatus] = mapped_column(
        Enum(
            ChannelOutboxStatus,
            name="channel_outbox_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=ChannelOutboxStatus.PENDING,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    channel_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_channel_outbox_drain", "status", "available_at"),
        CheckConstraint("attempts >= 0", name="ck_channel_outbox_attempts"),
    )


from app.models.customer import Customer  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sku import Sku  # noqa: E402
from app.models.tax_invoice import TaxInvoice  # noqa: E402
from app.models.user import User  # noqa: E402
