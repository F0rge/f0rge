from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class SkuBomLine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "sku_bom_lines"

    parent_sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    component_sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "parent_sku_id",
            "component_sku_id",
            name="uq_sku_bom_lines_parent_component",
        ),
        CheckConstraint("qty >= 1", name="ck_sku_bom_lines_qty"),
        CheckConstraint(
            "parent_sku_id <> component_sku_id",
            name="ck_sku_bom_lines_no_self_parent",
        ),
    )
