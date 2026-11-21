from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from app.services.settlement import SettlementStatus, bill_settlement_status
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class BillApprovalStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"


class Bill(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "bills"

    bill_number: Mapped[str] = mapped_column(String(128), nullable=False)
    is_archive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    cin7_source_payload: Mapped[Optional[dict[str, object]]] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fx_to_zar: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # False when the bill is in a foreign currency and no ZAR rate is known (Cin7 history).
    # Then ``fx_to_zar`` and ``amount_zar`` are 0 placeholders; ``currency`` and
    # ``amount_foreign`` hold the original amount. APIs return ZAR as null.
    fx_rate_known: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    amount_paid_zar: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    amount_paid_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payment_status: Mapped[SettlementStatus] = mapped_column(
        Enum(
            SettlementStatus,
            name="bill_payment_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=SettlementStatus.UNPAID,
        server_default=SettlementStatus.UNPAID.value,
    )
    # Legacy single attachment, copied into bill_attachments by 107. Kept for rollback.
    pdf_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    # Only approved bills are posted to the ledger and can be paid.
    approval_status: Mapped[BillApprovalStatus] = mapped_column(
        Enum(
            BillApprovalStatus,
            name="bill_approval_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=BillApprovalStatus.APPROVED,
        server_default=BillApprovalStatus.APPROVED.value,
    )
    # User archiving hides a bill from the active list; ``is_archive`` means a Cin7 import.
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["BillLine"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillLine.sort_order",
    )
    attachments: Mapped[list["BillAttachment"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="BillAttachment.uploaded_at",
    )

    __table_args__ = (
        UniqueConstraint("bill_number", name="uq_bills_bill_number"),
        # Target of tenant FKs; existing databases may carry it as 080's tenant_ref_* key.
        UniqueConstraint("team_id", "id", name="uq_bills_team_id_id"),
        CheckConstraint(
            "approval_status IN ('draft', 'awaiting_approval', 'approved')",
            name="ck_bills_approval_status",
        ),
        Index(
            "uq_bills_supplier_ref_ci",
            "team_id",
            "supplier_id",
            text("lower(supplier_ref)"),
            unique=True,
            postgresql_where=text("btrim(supplier_ref) <> '' AND NOT is_archive"),
        ),
    )


class BillLine(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "bill_lines"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_foreign: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    bill: Mapped[Bill] = relationship(back_populates="lines")


class BillAttachment(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "bill_attachments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "bill_id"],
            ["bills.team_id", "bills.id"],
            name="fk_bill_attachments_bill_tenant",
            ondelete="CASCADE",
        ),
    )

    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bill: Mapped[Bill] = relationship(back_populates="attachments")


@event.listens_for(Bill, "before_insert")
@event.listens_for(Bill, "before_update")
def _sync_bill_payment_status(_mapper, _connection, target: Bill) -> None:
    target.payment_status = bill_settlement_status(
        target.amount_paid_foreign or Decimal(0),
        target.amount_foreign,
        target.amount_paid_zar or Decimal(0),
        target.amount_zar,
    )


from app.models.supplier import Supplier  # noqa: E402
