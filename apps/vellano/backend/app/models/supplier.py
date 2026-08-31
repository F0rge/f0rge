from __future__ import annotations

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Supplier(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    __table_args__ = (
        Index(
            "ix_suppliers_name_lower",
            text("lower(name)"),
            unique=True,
        ),
    )
