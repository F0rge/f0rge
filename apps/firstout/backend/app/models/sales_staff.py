from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class SalesStaff(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    """A colleague credited with sales. Not a login: colleagues share till accounts."""

    __tablename__ = "sales_staff"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(32))
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal(0), server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_sales_staff_team_id_id"),
        CheckConstraint(
            "commission_rate >= 0 AND commission_rate <= 100", name="ck_sales_staff_rate"
        ),
    )
