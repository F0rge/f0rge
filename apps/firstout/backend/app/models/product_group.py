from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class ProductGroup(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_groups"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    options: Mapped[dict[str, list[str]]] = mapped_column(JSONB, nullable=False)
    storefront_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class ProductGroupVariant(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_group_variants"

    product_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_groups.id", ondelete="CASCADE"), nullable=False
    )
    source_sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False
    )
    options: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    option_signature: Mapped[str] = mapped_column(String(2048), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_sku_id", name="uq_product_group_variants_sku"),
        UniqueConstraint(
            "product_group_id", "option_signature", name="uq_product_group_variants_combination"
        ),
        Index("ix_product_group_variants_group_id", "product_group_id"),
    )
