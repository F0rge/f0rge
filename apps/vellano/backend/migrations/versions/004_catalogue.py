"""suppliers, proformas, skus catalogue tables.

Revision ID: 004_catalogue
Revises: 003_locations
Create Date: 2026-08-31

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_catalogue"
down_revision: Union[str, Sequence[str], None] = "003_locations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
    )
    op.create_index(
        "ix_suppliers_name_lower",
        "suppliers",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "proformas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("pdf_storage_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_proformas_supplier_id_suppliers",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_proformas"),
        sa.UniqueConstraint(
            "supplier_id",
            "invoice_number",
            name="uq_proformas_supplier_invoice",
        ),
    )
    op.create_index("ix_proformas_supplier_id", "proformas", ["supplier_id"])

    op.create_table(
        "skus",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("our_ref", sa.String(length=64), nullable=False),
        sa.Column("our_barcode", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("design", sa.String(length=255), nullable=False),
        sa.Column("fabric", sa.String(length=255), nullable=False),
        sa.Column("supplier_ref", sa.String(length=64), nullable=True),
        sa.Column("photo_storage_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_skus"),
        sa.UniqueConstraint("our_ref", name="uq_skus_our_ref"),
        sa.UniqueConstraint("our_barcode", name="uq_skus_our_barcode"),
    )
    op.create_index(
        "ix_skus_design_fabric_lower",
        "skus",
        [sa.text("lower(design)"), sa.text("lower(fabric)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_skus_design_fabric_lower", table_name="skus")
    op.drop_table("skus")
    op.drop_index("ix_proformas_supplier_id", table_name="proformas")
    op.drop_table("proformas")
    op.drop_index("ix_suppliers_name_lower", table_name="suppliers")
    op.drop_table("suppliers")
