from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class CategoryAccountMap(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "category_account_maps"

    category: Mapped[str] = mapped_column(String(64), nullable=False)
    sales_code: Mapped[str] = mapped_column(String(16), nullable=False)
    cogs_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_adj_code: Mapped[str] = mapped_column(String(16), nullable=False)
    count_var_code: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (UniqueConstraint("category", name="uq_category_account_maps_category"),)
