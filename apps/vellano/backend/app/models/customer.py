from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Customer(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vat_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    billing_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
