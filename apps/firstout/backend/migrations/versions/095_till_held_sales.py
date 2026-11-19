"""Store showroom-held till baskets and content-free retry receipts.

Revision ID: 095_till_held_sales
Revises: 094_personal_mcp_tokens
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "095_till_held_sales"
down_revision = "094_personal_mcp_tokens"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "held_sales",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True)),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("held_by_name", sa.String(255), nullable=False),
        sa.Column(
            "held_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.String(500)),
        sa.Column("estimated_total_inc_vat", sa.Numeric(24, 2)),
        sa.Column("pick_id", UUID(as_uuid=True)),
        sa.Column("linked_pick_ids", JSONB, nullable=False),
        sa.Column("lines", JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_held_sales_showroom_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version >= 1", name="ck_held_sales_version"),
    )
    op.create_index("ix_held_sales_team_id", "held_sales", ["team_id"])
    op.create_index(
        "ix_held_sales_showroom_held_at", "held_sales", ["team_id", "location_id", "held_at"]
    )
    op.create_table(
        "held_sale_operations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("location_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("held_sale_id", UUID(as_uuid=True), nullable=False),
        sa.Column("held_current_id", UUID(as_uuid=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id", "location_id"],
            ["locations.team_id", "locations.id"],
            name="fk_held_sale_operations_showroom_tenant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "team_id",
            "location_id",
            "actor_id",
            "action",
            "operation_id",
            name="uq_held_sale_operations_scope",
        ),
    )
    op.create_index("ix_held_sale_operations_team_id", "held_sale_operations", ["team_id"])
    op.create_index(
        "ix_held_sale_operations_expiry",
        "held_sale_operations",
        ["team_id", "location_id", "expires_at"],
    )
    for table in ("held_sales", "held_sale_operations"):
        predicate = f"team_id = {_TENANT_VALUE}"
        op.execute(
            f"CREATE POLICY organisation_isolation ON {table} FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                       AND relrowsecurity AND relforcerowsecurity) THEN
                ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            END IF;
        END $$""")


def downgrade() -> None:
    # Roll back the app while retaining these tables if held baskets must survive.
    op.drop_table("held_sale_operations")
    op.drop_table("held_sales")
