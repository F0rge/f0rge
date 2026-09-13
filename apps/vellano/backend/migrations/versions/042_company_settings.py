"""Company settings, document sequences, customer terms, invoice due date.

Revision ID: 042_company_settings
Revises: 041_nia_schedule
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "042_company_settings"
down_revision: Union[str, Sequence[str], None] = "041_nia_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DOCUMENT_SEQUENCE_SEED_SQL = """
INSERT INTO document_sequences (
    id,
    team_id,
    doc_type,
    prefix,
    padding,
    next_value,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    teams.id,
    seeds.doc_type,
    seeds.prefix,
    4,
    COALESCE(seeds.max_num, 0) + 1,
    NOW(),
    NOW()
FROM teams
CROSS JOIN LATERAL (
    SELECT
        'invoice'::text AS doc_type,
        'INV'::text AS prefix,
        (
            SELECT MAX(CAST(SPLIT_PART(invoice_number, '-', 2) AS BIGINT))
            FROM tax_invoices
            WHERE invoice_number ~ '^INV-[0-9]+$'
        ) AS max_num
    UNION ALL
    SELECT
        'credit_note',
        'CN',
        (
            SELECT MAX(CAST(SPLIT_PART(credit_note_number, '-', 2) AS BIGINT))
            FROM credit_notes
            WHERE credit_note_number ~ '^CN-[0-9]+$'
        )
    UNION ALL
    SELECT
        'bill',
        'BILL',
        (
            SELECT MAX(CAST(SPLIT_PART(bill_number, '-', 2) AS BIGINT))
            FROM bills
            WHERE bill_number ~ '^BILL-[0-9]+$'
        )
    UNION ALL
    SELECT
        'payment',
        'PAY',
        (
            SELECT MAX(CAST(SPLIT_PART(payment_number, '-', 2) AS BIGINT))
            FROM payments
            WHERE payment_number ~ '^PAY-[0-9]+$'
        )
    UNION ALL
    SELECT
        'purchase_order',
        'PO',
        (
            SELECT MAX(CAST(SPLIT_PART(po_number, '-', 2) AS BIGINT))
            FROM purchase_orders
            WHERE po_number ~ '^PO-[0-9]+$'
        )
    UNION ALL
    SELECT
        'delivery',
        'DLV',
        (
            SELECT MAX(CAST(SPLIT_PART(delivery_number, '-', 2) AS BIGINT))
            FROM deliveries
            WHERE delivery_number ~ '^DLV-[0-9]+$'
        )
    UNION ALL
    SELECT
        'stock_return',
        'RTN',
        (
            SELECT MAX(CAST(SPLIT_PART(return_number, '-', 2) AS BIGINT))
            FROM stock_returns
            WHERE return_number ~ '^RTN-[0-9]+$'
        )
    UNION ALL
    SELECT
        'journal',
        'JE',
        (
            SELECT MAX(CAST(SPLIT_PART(journal_number, '-', 2) AS BIGINT))
            FROM journal_entries
            WHERE journal_number IS NOT NULL
              AND journal_number ~ '^JE-[0-9]+$'
        )
    UNION ALL
    SELECT
        'layby',
        'LB',
        (
            SELECT MAX(CAST(SPLIT_PART(layby_number, '-', 2) AS BIGINT))
            FROM laybys
            WHERE layby_number ~ '^LB-[0-9]+$'
        )
    UNION ALL
    SELECT
        'transfer',
        'TRF',
        (
            SELECT MAX(CAST(SPLIT_PART(transfer_number, '-', 2) AS BIGINT))
            FROM transfers
            WHERE transfer_number ~ '^TRF-[0-9]+$'
        )
    UNION ALL
    SELECT
        'pick',
        'PCK',
        (
            SELECT MAX(CAST(SPLIT_PART(number, '-', 2) AS BIGINT))
            FROM picks
            WHERE number ~ '^PCK-[0-9]+$'
        )
) AS seeds
"""


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "legal_name",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Vellano'"),
        ),
    )
    op.add_column("team_settings", sa.Column("trading_name", sa.Text(), nullable=True))
    op.add_column(
        "team_settings",
        sa.Column(
            "address",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Kramerville, Johannesburg, South Africa'"),
        ),
    )
    op.add_column(
        "team_settings",
        sa.Column(
            "vat_number",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'4123456789'"),
        ),
    )
    op.add_column("team_settings", sa.Column("cipc_number", sa.Text(), nullable=True))
    op.add_column("team_settings", sa.Column("bank_name", sa.Text(), nullable=True))
    op.add_column("team_settings", sa.Column("bank_account", sa.Text(), nullable=True))
    op.add_column("team_settings", sa.Column("bank_branch_code", sa.Text(), nullable=True))
    op.add_column(
        "team_settings",
        sa.Column(
            "payment_terms_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
        ),
    )
    op.add_column(
        "team_settings",
        sa.Column("default_receive_location_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("default_till_location_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_team_settings_default_receive_location_id_locations",
        "team_settings",
        "locations",
        ["default_receive_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_team_settings_default_till_location_id_locations",
        "team_settings",
        "locations",
        ["default_till_location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("customers", sa.Column("payment_terms_days", sa.Integer(), nullable=True))
    op.add_column("tax_invoices", sa.Column("due_date", sa.Date(), nullable=True))

    op.create_table(
        "document_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "padding",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("4"),
        ),
        sa.Column("next_value", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_document_sequences_team_id_teams",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_sequences"),
        sa.UniqueConstraint("team_id", "doc_type", name="uq_document_sequences_team_doc_type"),
    )
    op.create_index("ix_document_sequences_team_id", "document_sequences", ["team_id"])

    op.execute(sa.text(_DOCUMENT_SEQUENCE_SEED_SQL))


def downgrade() -> None:
    op.drop_index("ix_document_sequences_team_id", table_name="document_sequences")
    op.drop_table("document_sequences")

    op.drop_column("tax_invoices", "due_date")
    op.drop_column("customers", "payment_terms_days")

    op.drop_constraint(
        "fk_team_settings_default_till_location_id_locations",
        "team_settings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_team_settings_default_receive_location_id_locations",
        "team_settings",
        type_="foreignkey",
    )
    op.drop_column("team_settings", "default_till_location_id")
    op.drop_column("team_settings", "default_receive_location_id")
    op.drop_column("team_settings", "payment_terms_days")
    op.drop_column("team_settings", "bank_branch_code")
    op.drop_column("team_settings", "bank_account")
    op.drop_column("team_settings", "bank_name")
    op.drop_column("team_settings", "cipc_number")
    op.drop_column("team_settings", "vat_number")
    op.drop_column("team_settings", "address")
    op.drop_column("team_settings", "trading_name")
    op.drop_column("team_settings", "legal_name")
