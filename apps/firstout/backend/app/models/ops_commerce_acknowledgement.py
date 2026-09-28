from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class OpsCommerceAcknowledgement(UUIDPkMixin, TimestampMixin, Base):
    """A channel line whose stock deduction was committed in the same Ops transaction.

    The future paid-order importer owns writes. This table has no public mutation route.
    """

    __tablename__ = "ops_commerce_acknowledgements"

    commitment_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_ops_commerce_acknowledgements_quantity"),
        Index("ix_ops_commerce_acknowledgements_source_sku_id", "source_sku_id"),
    )
