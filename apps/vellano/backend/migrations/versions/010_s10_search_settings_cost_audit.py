"""S10 team settings and unit cost audit.

Revision ID: 010_s10_cockpit
Revises: 009_till_tender
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_s10_cockpit"
down_revision: Union[str, Sequence[str], None] = "009_till_tender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("home_currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_team_settings_team_id"),
    )

    op.create_table(
        "unit_cost_audit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sku_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("po_id", sa.UUID(), nullable=True),
        sa.Column("po_line_id", sa.UUID(), nullable=True),
        sa.Column("old_cost_zar", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("new_cost_zar", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "land",
                "receive",
                "correction",
                name="unit_cost_audit_source",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["po_line_id"], ["po_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_unit_cost_audit_sku_id", "unit_cost_audit", ["sku_id"])


def downgrade() -> None:
    op.drop_index("ix_unit_cost_audit_sku_id", table_name="unit_cost_audit")
    op.drop_table("unit_cost_audit")
    op.drop_table("team_settings")
    op.execute("DROP TYPE IF EXISTS unit_cost_audit_source")
