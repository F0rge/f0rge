from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class TaxRule(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tax_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tax_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    account_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    percent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
