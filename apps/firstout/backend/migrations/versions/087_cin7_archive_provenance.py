"""Retain canonical archive source rows and scope live supplier-reference checks.

Revision ID: 087_cin7_archive_provenance
Revises: 086_cin7_sellability

Downgrade refuses to discard any source payload, restore an index that would
conflict with retained archive references, or invent a missing purchase unit
amount. Roll application code back while retaining this source data, or use a
separately reviewed recovery plan.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from f0rge_db.rls import migration_bypass
from sqlalchemy.dialects import postgresql

revision = "087_cin7_archive_provenance"
down_revision = "086_cin7_sellability"
branch_labels = None
depends_on = None

SOURCE_TABLES = (
    "tax_invoices",
    "archive_credit_notes",
    "sales_orders",
    "purchase_orders",
    "bills",
)
PREFLIGHT_TABLES = (*SOURCE_TABLES, "po_lines")
SUPPLIER_REF_INDEX = "uq_bills_supplier_ref_ci"


def _supplier_ref_index(*, live_only: bool) -> None:
    predicate = "btrim(supplier_ref) <> ''"
    if live_only:
        predicate += " AND NOT is_archive"
    op.create_index(
        SUPPLIER_REF_INDEX,
        "bills",
        ["team_id", "supplier_id", sa.text("lower(supplier_ref)")],
        unique=True,
        postgresql_where=sa.text(predicate),
    )


def upgrade() -> None:
    op.alter_column(
        "po_lines", "factory_unit_amount", existing_type=sa.Numeric(18, 4), nullable=True
    )
    for table in SOURCE_TABLES:
        op.add_column(
            table,
            sa.Column("cin7_source_payload", postgresql.JSONB(none_as_null=True), nullable=True),
        )
    # Migration 080 retained this index name and prepended team_id. Keep the
    # existing live uniqueness key; only archives are outside its predicate.
    op.drop_index(SUPPLIER_REF_INDEX, table_name="bills")
    _supplier_ref_index(live_only=True)


def downgrade() -> None:
    bind = op.get_bind()
    tables_sql = ", ".join(f'"{table}"' for table in sorted(PREFLIGHT_TABLES))
    bind.execute(sa.text(f"LOCK TABLE {tables_sql} IN ACCESS EXCLUSIVE MODE"))
    with migration_bypass(bind, PREFLIGHT_TABLES):
        for table in SOURCE_TABLES:
            if bind.scalar(
                sa.text(
                    f'SELECT EXISTS (SELECT 1 FROM "{table}" WHERE cin7_source_payload IS NOT NULL)'
                )
            ):
                raise RuntimeError(
                    "Cannot downgrade 087_cin7_archive_provenance: "
                    f"{table} retains Cin7 source payloads; use a reviewed recovery plan"
                )
        if bind.scalar(
            sa.text("SELECT EXISTS (SELECT 1 FROM po_lines WHERE factory_unit_amount IS NULL)")
        ):
            raise RuntimeError(
                "Cannot downgrade 087_cin7_archive_provenance: "
                "purchase lines retain unknown factory unit amounts"
            )
        if bind.scalar(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM bills WHERE btrim(supplier_ref) <> '' "
                "GROUP BY team_id, supplier_id, lower(supplier_ref) HAVING count(*) > 1)"
            )
        ):
            raise RuntimeError(
                "Cannot downgrade 087_cin7_archive_provenance: "
                "retained supplier references conflict with the previous unique index"
            )
    op.drop_index(SUPPLIER_REF_INDEX, table_name="bills")
    _supplier_ref_index(live_only=False)
    op.alter_column(
        "po_lines", "factory_unit_amount", existing_type=sa.Numeric(18, 4), nullable=False
    )
    for table in reversed(SOURCE_TABLES):
        op.drop_column(table, "cin7_source_payload")
