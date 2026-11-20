"""Reserve company stock for open baskets and expire them.

Revision ID: 099_stock_reservations
Revises: 098_till_baskets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "099_stock_reservations"
down_revision = "098_till_baskets"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column("till_baskets", sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.add_column("till_baskets", sa.Column("expired_at", sa.DateTime(timezone=True)))
    op.create_table(
        "stock_reservations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column(
            "sku_id",
            UUID(as_uuid=True),
            sa.ForeignKey("skus.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("holder_kind", sa.String(16), nullable=False),
        sa.Column("holder_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_stock_reservations_showroom_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "team_id",
            "holder_kind",
            "holder_id",
            "sku_id",
            name="uq_stock_reservations_holder_sku",
        ),
        sa.CheckConstraint("qty > 0", name="ck_stock_reservations_qty"),
        sa.CheckConstraint(
            "holder_kind IN ('basket', 'held_sale', 'invoice')",
            name="ck_stock_reservations_holder_kind",
        ),
    )
    op.create_index("ix_stock_reservations_team_id", "stock_reservations", ["team_id"])
    op.create_index("ix_stock_reservations_sku", "stock_reservations", ["team_id", "sku_id"])
    op.create_index(
        "ix_stock_reservations_holder",
        "stock_reservations",
        ["team_id", "holder_kind", "holder_id"],
    )
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON stock_reservations FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE stock_reservations ENABLE ROW LEVEL SECURITY;
            ALTER TABLE stock_reservations FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")


def downgrade() -> None:
    op.drop_table("stock_reservations")
    op.drop_column("till_baskets", "expired_at")
    op.drop_column("till_baskets", "expires_at")
