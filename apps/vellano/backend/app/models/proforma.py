from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class Proforma(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "proformas"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pdf_storage_key: Mapped[str] = mapped_column(String, nullable=False)

    supplier: Mapped["Supplier"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "invoice_number",
            name="uq_proformas_supplier_invoice",
        ),
        Index("ix_proformas_supplier_id", "supplier_id"),
    )


from app.models.supplier import Supplier  # noqa: E402
