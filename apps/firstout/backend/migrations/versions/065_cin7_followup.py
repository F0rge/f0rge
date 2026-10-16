"""Cin7 follow-up: party addresses/contacts, decimal BOM, archive credit notes, bill FX flag.

Revision ID: 065_cin7_followup
Revises: 064_cin7_import
Create Date: 2026-10-16

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "065_cin7_followup"
down_revision: Union[str, Sequence[str], None] = "064_cin7_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _address_cols() -> list[sa.Column]:
    return [
        sa.Column("natural_key", sa.String(64), nullable=False),
        sa.Column("address_type", sa.String(32), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("line1", sa.Text(), nullable=True),
        sa.Column("line2", sa.Text(), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("state", sa.String(128), nullable=True),
        sa.Column("postcode", sa.String(32), nullable=True),
        sa.Column("country", sa.String(128), nullable=True),
    ]


def _contact_cols() -> list[sa.Column]:
    return [
        sa.Column("natural_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("mobile", sa.String(64), nullable=True),
        sa.Column("fax", sa.String(64), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "include_in_emails", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    ]


def _party_table(name: str, owner: str, cols: list[sa.Column]) -> None:
    fk = f"{owner}_id"
    op.create_table(
        name,
        *_base(),
        sa.Column(fk, postgresql.UUID(as_uuid=True), nullable=False),
        *cols,
        sa.ForeignKeyConstraint([fk], [f"{owner}s.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(fk, "natural_key", name=f"uq_{name}_key"),
    )
    op.create_index(f"ix_{name}_{fk}", name, [fk])


def upgrade() -> None:
    _party_table("customer_addresses", "customer", _address_cols())
    _party_table(
        "customer_contacts",
        "customer",
        _contact_cols() + [sa.Column("marketing_consent", sa.String(64), nullable=True)],
    )
    _party_table("supplier_addresses", "supplier", _address_cols())
    _party_table("supplier_contacts", "supplier", _contact_cols())

    op.drop_constraint("ck_sku_bom_lines_qty", "sku_bom_lines", type_="check")
    op.alter_column(
        "sku_bom_lines",
        "qty",
        existing_type=sa.Integer(),
        type_=sa.Numeric(14, 4),
        existing_nullable=False,
    )
    op.create_check_constraint("ck_sku_bom_lines_qty", "sku_bom_lines", "qty > 0")

    op.add_column(
        "bills",
        sa.Column("fx_rate_known", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    # 064 stored non-ZAR archive bills with fx_to_zar 0: their ZAR value is unknown.
    op.execute("UPDATE bills SET fx_rate_known = false WHERE is_archive AND fx_to_zar = 0")

    op.create_table(
        "archive_credit_notes",
        *_base(),
        sa.Column("document_number", sa.String(64), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("subtotal_ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_inc_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="cin7"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_number", name="uq_archive_credit_notes_number"),
    )
    op.create_index("ix_archive_credit_notes_customer_id", "archive_credit_notes", ["customer_id"])
    op.create_index("ix_archive_credit_notes_issue_date", "archive_credit_notes", ["issue_date"])
    op.create_table(
        "archive_credit_note_lines",
        *_base(),
        sa.Column("credit_note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku_code", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(14, 4), nullable=False),
        sa.Column("ex_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("inc_vat", sa.Numeric(14, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["credit_note_id"], ["archive_credit_notes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_archive_credit_note_lines_credit_note_id",
        "archive_credit_note_lines",
        ["credit_note_id"],
    )
    op.create_index("ix_archive_credit_note_lines_sku_id", "archive_credit_note_lines", ["sku_id"])


def downgrade() -> None:
    op.drop_table("archive_credit_note_lines")
    op.drop_table("archive_credit_notes")
    op.drop_column("bills", "fx_rate_known")
    op.drop_constraint("ck_sku_bom_lines_qty", "sku_bom_lines", type_="check")
    # Fractional BOM lines cannot survive the integer column.
    op.execute("DELETE FROM sku_bom_lines WHERE qty <> trunc(qty)")
    op.alter_column(
        "sku_bom_lines",
        "qty",
        existing_type=sa.Numeric(14, 4),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="qty::integer",
    )
    op.create_check_constraint("ck_sku_bom_lines_qty", "sku_bom_lines", "qty >= 1")
    for name in (
        "supplier_contacts",
        "supplier_addresses",
        "customer_contacts",
        "customer_addresses",
    ):
        op.drop_table(name)
