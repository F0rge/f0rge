from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import UUIDPkMixin


class HeldSaleOperation(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "held_sale_operations"

    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(12))
    request_hash: Mapped[str] = mapped_column(String(64))
    # Receipts contain IDs and a fingerprint, never a deleted basket's contents.
    held_sale_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    held_current_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_held_sale_operations_showroom_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "team_id",
            "location_id",
            "actor_id",
            "action",
            "operation_id",
            name="uq_held_sale_operations_scope",
        ),
        Index("ix_held_sale_operations_expiry", "team_id", "location_id", "expires_at"),
    )
