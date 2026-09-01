"""Two-step transfer documents (draft → in_transit → received).

Revision ID: 031_two_step_transfers
Revises: 030_sku_carton_bom
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031_two_step_transfers"
down_revision: Union[str, Sequence[str], None] = "030_sku_carton_bom"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_number", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("from_location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("dispatched_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("received_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_display_name", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["from_location_id"],
            ["locations.id"],
            name="fk_transfers_from_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_location_id"],
            ["locations.id"],
            name="fk_transfers_to_location_id_locations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_transfers_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dispatched_by_user_id"],
            ["users.id"],
            name="fk_transfers_dispatched_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["received_by_user_id"],
            ["users.id"],
            name="fk_transfers_received_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transfers"),
        sa.UniqueConstraint("transfer_number", name="uq_transfers_transfer_number"),
        sa.CheckConstraint(
            "status IN ('draft', 'in_transit', 'received', 'cancelled')",
            name="ck_transfers_status",
        ),
        sa.CheckConstraint(
            "from_location_id != to_location_id",
            name="ck_transfers_distinct_locations",
        ),
    )
    op.create_index("ix_transfers_from_location_id", "transfers", ["from_location_id"])
    op.create_index("ix_transfers_to_location_id", "transfers", ["to_location_id"])
    op.create_index("ix_transfers_created_by_user_id", "transfers", ["created_by_user_id"])
    op.create_index("ix_transfers_status", "transfers", ["status"])

    op.create_table(
        "transfer_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qty_dispatched", sa.Integer(), nullable=False),
        sa.Column("qty_received", sa.Integer(), nullable=True),
        sa.Column("from_bin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_bin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_cost_zar", sa.Numeric(18, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["transfers.id"],
            name="fk_transfer_lines_transfer_id_transfers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sku_id"],
            ["skus.id"],
            name="fk_transfer_lines_sku_id_skus",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_bin_id"],
            ["location_bins.id"],
            name="fk_transfer_lines_from_bin_id_location_bins",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_bin_id"],
            ["location_bins.id"],
            name="fk_transfer_lines_to_bin_id_location_bins",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transfer_lines"),
        sa.CheckConstraint("qty_dispatched > 0", name="ck_transfer_lines_qty_dispatched"),
        sa.CheckConstraint(
            "qty_received IS NULL OR qty_received >= 0",
            name="ck_transfer_lines_qty_received",
        ),
    )
    op.create_index("ix_transfer_lines_transfer_id", "transfer_lines", ["transfer_id"])


def downgrade() -> None:
    op.drop_index("ix_transfer_lines_transfer_id", table_name="transfer_lines")
    op.drop_table("transfer_lines")
    op.drop_index("ix_transfers_status", table_name="transfers")
    op.drop_index("ix_transfers_created_by_user_id", table_name="transfers")
    op.drop_index("ix_transfers_to_location_id", table_name="transfers")
    op.drop_index("ix_transfers_from_location_id", table_name="transfers")
    op.drop_table("transfers")
