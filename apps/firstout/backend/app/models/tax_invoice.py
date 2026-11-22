from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
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
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.tenant import TenantOwnedMixin
from app.services.settlement import SettlementStatus, settlement_status
from f0rge_db.mixins import TimestampMixin, UUIDPkMixin


class TaxInvoice(TenantOwnedMixin, UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tax_invoices"

    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    subtotal_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    total_inc_vat: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    payment_status: Mapped[SettlementStatus] = mapped_column(
        Enum(
            SettlementStatus,
            name="invoice_payment_status",
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        default=SettlementStatus.UNPAID,
        server_default=SettlementStatus.UNPAID.value,
    )
    prices_include_vat: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    is_archive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Issued unpaid to go on the customer's statement; reads "On statement" until a payment.
    on_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Printed on the tax invoice the customer receives.
    note_printed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Staff only; never printed.
    note_internal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The colleague credited with the sale (commission).
    sales_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    # "till" or "manual". Cin7 imports are told apart by is_archive, not by this.
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", server_default="manual"
    )
    # Staff archiving only hides the invoice from the default list; it stays in the books.
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_tax_invoices_archived_by_id_users"),
        nullable=True,
    )
    cin7_source_payload: Mapped[Optional[dict[str, object]]] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )

    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.sort_order",
    )
    credit_note: Mapped[Optional["CreditNote"]] = relationship(  # noqa: F821
        "CreditNote",
        back_populates="invoice",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_tax_invoices_invoice_number"),
        # Target of tenant FKs; existing databases carry it as 080's tenant_ref_* key.
        UniqueConstraint("team_id", "id", name="uq_tax_invoices_team_id_id"),
        ForeignKeyConstraint(
            ["team_id", "sales_staff_id"],
            ["sales_staff.team_id", "sales_staff.id"],
            name="fk_tax_invoices_sales_staff_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_tax_invoices_sales_staff", "team_id", "sales_staff_id"),
    )


class InvoiceLine(TenantOwnedMixin, UUIDPkMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ex_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    inc_vat: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sku_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skus.id", ondelete="RESTRICT"),
        nullable=True,
    )
    price_warning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Unit cost of goods the sale booked for this line, so a return restocks at that cost.
    # None when no single cost applies (kits, part-picked lines, books invoices, older sales).
    unit_cost_zar: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    # Snapshot from the till sale. Later catalogue changes do not determine restock eligibility.
    till_no_stock_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Snapshot of the SKU's flag at sale time, so later SKU edits leave past commission alone.
    exclude_from_commission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    invoice: Mapped[TaxInvoice] = relationship(back_populates="lines")


@event.listens_for(InvoiceLine, "before_insert")
def _snapshot_commission_exclusion(_mapper, connection, target: InvoiceLine) -> None:
    """Every invoice path (till, manual, laybys, orders) snapshots the SKU flag here."""
    # ponytail: one PK lookup per SKU line; batch it if bulk invoice imports ever matter.
    if target.sku_id is None:
        return
    from app.models.sku import Sku

    target.exclude_from_commission = bool(
        connection.scalar(select(Sku.exclude_from_commission).where(Sku.id == target.sku_id))
    )


@event.listens_for(TaxInvoice, "before_insert")
@event.listens_for(TaxInvoice, "before_update")
def _sync_invoice_payment_status(_mapper, _connection, target: TaxInvoice) -> None:
    target.payment_status = settlement_status(target.amount_paid, target.total_inc_vat)


from app.models.customer import Customer  # noqa: E402
