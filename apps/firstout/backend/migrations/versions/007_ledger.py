"""S6 ledger: chart of accounts, customers, journals, invoices, bills, payments.

Revision ID: 007_ledger
Revises: 006_sku_prices
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_ledger"
down_revision: Union[str, Sequence[str], None] = "006_sku_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCOUNT_TYPES = ("asset", "liability", "income", "expense")
JOURNAL_DOCUMENT_TYPES = ("invoice", "credit_note", "bill", "payment")
PAYMENT_DIRECTIONS = ("in", "out")

CHART_OF_ACCOUNTS = (
    ("1100", "Bank", "asset"),
    ("1200", "Accounts receivable", "asset"),
    ("1300", "Inventory", "asset"),
    ("2100", "Accounts payable", "liability"),
    ("2200", "VAT control", "liability"),
    ("4000", "Sales", "income"),
    ("5000", "Cost of goods sold", "expense"),
    ("6100", "Foreign exchange gain/loss", "expense"),
)


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
        sa.CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in ACCOUNT_TYPES)})",
            name="ck_accounts_type",
        ),
    )

    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("vat_number", sa.String(length=64), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
    )

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memo", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_journal_entries"),
        sa.CheckConstraint(
            f"document_type IN ({', '.join(repr(t) for t in JOURNAL_DOCUMENT_TYPES)})",
            name="ck_journal_entries_document_type",
        ),
    )
    op.create_index("ix_journal_entries_document_id", "journal_entries", ["document_id"])

    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("debit_zar", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("credit_zar", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_journal_lines_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["journal_entries.id"],
            name="fk_journal_lines_entry_id_journal_entries",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_journal_lines"),
        sa.CheckConstraint(
            "(debit_zar > 0 AND credit_zar = 0) OR (credit_zar > 0 AND debit_zar = 0)",
            name="ck_journal_lines_debit_or_credit",
        ),
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])

    op.create_table(
        "tax_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "amount_paid",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_tax_invoices_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tax_invoices"),
        sa.UniqueConstraint("invoice_number", name="uq_tax_invoices_invoice_number"),
    )
    op.create_index("ix_tax_invoices_customer_id", "tax_invoices", ["customer_id"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("inc_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_invoice_lines_invoice_id_tax_invoices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credit_note_number", sa.String(length=32), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_credit_notes_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_credit_notes"),
        sa.UniqueConstraint("credit_note_number", name="uq_credit_notes_credit_note_number"),
        sa.UniqueConstraint("invoice_id", name="uq_credit_notes_invoice_id"),
    )
    op.create_index("ix_credit_notes_invoice_id", "credit_notes", ["invoice_id"])

    op.create_table(
        "bills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_number", sa.String(length=32), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_ref", sa.String(length=128), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("fx_to_zar", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("amount_foreign", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount_zar", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "amount_paid_zar",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("pdf_storage_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_bills_supplier_id_suppliers",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bills"),
        sa.UniqueConstraint("bill_number", name="uq_bills_bill_number"),
    )
    op.create_index("ix_bills_supplier_id", "bills", ["supplier_id"])

    op.create_table(
        "bill_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount_foreign", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name="fk_bill_lines_bill_id_bills",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bill_lines"),
    )
    op.create_index("ix_bill_lines_bill_id", "bill_lines", ["bill_id"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_number", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "fx_to_zar",
            sa.Numeric(precision=14, scale=6),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("amount_zar", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "fx_gain_loss_zar",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["bills.id"],
            name="fk_payments_bill_id_bills",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_payments_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("payment_number", name="uq_payments_payment_number"),
        sa.CheckConstraint(
            "(direction = 'in' AND invoice_id IS NOT NULL AND bill_id IS NULL) OR "
            "(direction = 'out' AND bill_id IS NOT NULL AND invoice_id IS NULL)",
            name="ck_payments_direction_target",
        ),
        sa.CheckConstraint(
            f"direction IN ({', '.join(repr(t) for t in PAYMENT_DIRECTIONS)})",
            name="ck_payments_direction",
        ),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])
    op.create_index("ix_payments_bill_id", "payments", ["bill_id"])

    now = datetime.datetime.utcnow()
    accounts = sa.table(
        "accounts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("is_archived", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        accounts,
        [
            {
                "id": uuid.uuid4(),
                "code": code,
                "name": name,
                "type": account_type,
                "is_system": True,
                "is_archived": False,
                "created_at": now,
                "updated_at": now,
            }
            for code, name, account_type in CHART_OF_ACCOUNTS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_bill_id", table_name="payments")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_bill_lines_bill_id", table_name="bill_lines")
    op.drop_table("bill_lines")
    op.drop_index("ix_bills_supplier_id", table_name="bills")
    op.drop_table("bills")
    op.drop_index("ix_credit_notes_invoice_id", table_name="credit_notes")
    op.drop_table("credit_notes")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_tax_invoices_customer_id", table_name="tax_invoices")
    op.drop_table("tax_invoices")
    op.drop_index("ix_journal_lines_account_id", table_name="journal_lines")
    op.drop_index("ix_journal_lines_entry_id", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_document_id", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_table("customers")
    op.drop_table("accounts")
