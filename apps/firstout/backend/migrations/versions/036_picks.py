"""Multi-location kit picks and pick settings.

Revision ID: 036_picks
Revises: 035_po_lead_timestamps
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036_picks"
down_revision: Union[str, Sequence[str], None] = "035_po_lead_timestamps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "always_prefer_warehouse",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "team_settings",
        sa.Column(
            "pick_priority",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_table(
        "picks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kit_sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kit_qty", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("staging_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kit_sku_id"],
            ["skus.id"],
            name="fk_picks_kit_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["staging_location_id"],
            ["locations.id"],
            name="fk_picks_staging_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name="fk_picks_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["tax_invoices.id"],
            name="fk_picks_invoice_id_tax_invoices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_picks"),
        sa.UniqueConstraint("number", name="uq_picks_number"),
        sa.CheckConstraint("kit_qty > 0", name="ck_picks_kit_qty"),
        sa.CheckConstraint(
            "source_type IN ('invoice', 'layby', 'till')",
            name="ck_picks_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'picking', 'staged', 'cancelled')",
            name="ck_picks_status",
        ),
    )
    op.create_index("ix_picks_kit_sku_id", "picks", ["kit_sku_id"])
    op.create_index("ix_picks_invoice_id", "picks", ["invoice_id"])

    op.create_table(
        "pick_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pick_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty_needed", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pick_id"],
            ["picks.id"],
            name="fk_pick_lines_pick_id_picks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_pick_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pick_lines"),
        sa.CheckConstraint("qty_needed > 0", name="ck_pick_lines_qty_needed"),
    )
    op.create_index("ix_pick_lines_pick_id", "pick_lines", ["pick_id"])

    op.create_table(
        "pick_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pick_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pick_line_id"],
            ["pick_lines.id"],
            name="fk_pick_allocations_pick_line_id_pick_lines",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_pick_allocations_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pick_allocations"),
        sa.CheckConstraint("qty > 0", name="ck_pick_allocations_qty"),
    )
    op.create_index("ix_pick_allocations_pick_line_id", "pick_allocations", ["pick_line_id"])
    op.create_index("ix_pick_allocations_location_id", "pick_allocations", ["location_id"])

    op.add_column(
        "transfers",
        sa.Column("pick_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transfers_pick_id_picks",
        "transfers",
        "picks",
        ["pick_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transfers_pick_id", "transfers", ["pick_id"])


def downgrade() -> None:
    op.drop_index("ix_transfers_pick_id", table_name="transfers")
    op.drop_constraint("fk_transfers_pick_id_picks", "transfers", type_="foreignkey")
    op.drop_column("transfers", "pick_id")
    op.drop_index("ix_pick_allocations_location_id", table_name="pick_allocations")
    op.drop_index("ix_pick_allocations_pick_line_id", table_name="pick_allocations")
    op.drop_table("pick_allocations")
    op.drop_index("ix_pick_lines_pick_id", table_name="pick_lines")
    op.drop_table("pick_lines")
    op.drop_index("ix_picks_invoice_id", table_name="picks")
    op.drop_index("ix_picks_kit_sku_id", table_name="picks")
    op.drop_table("picks")
    op.drop_column("team_settings", "pick_priority")
    op.drop_column("team_settings", "always_prefer_warehouse")
