"""Record when each SKU's till reservations last changed, for the ops availability revision.

Revision ID: 101_stock_reservation_changes
Revises: 100_held_sale_expiry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "101_stock_reservation_changes"
down_revision = "100_held_sale_expiry"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "stock_reservation_changes",
        sa.Column(
            "team_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text(_TENANT_VALUE),
        ),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("team_id", "sku_id"),
    )
    op.create_index(
        "ix_stock_reservation_changes_team_id", "stock_reservation_changes", ["team_id"]
    )
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON stock_reservation_changes FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE stock_reservation_changes ENABLE ROW LEVEL SECURITY;
            ALTER TABLE stock_reservation_changes FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")
    # Reservations written by the database, not by a code path that could forget the mark.
    op.execute("""
CREATE FUNCTION mark_stock_reservation_change() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        INSERT INTO stock_reservation_changes (team_id, sku_id, changed_at)
        VALUES (OLD.team_id, OLD.sku_id, clock_timestamp())
        ON CONFLICT (team_id, sku_id) DO UPDATE SET changed_at = EXCLUDED.changed_at;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        INSERT INTO stock_reservation_changes (team_id, sku_id, changed_at)
        VALUES (NEW.team_id, NEW.sku_id, clock_timestamp())
        ON CONFLICT (team_id, sku_id) DO UPDATE SET changed_at = EXCLUDED.changed_at;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql
""")
    op.execute("""
CREATE TRIGGER stock_reservations_mark_change
AFTER INSERT OR UPDATE OR DELETE ON stock_reservations
FOR EACH ROW EXECUTE FUNCTION mark_stock_reservation_change()
""")


def downgrade() -> None:
    op.execute("DROP TRIGGER stock_reservations_mark_change ON stock_reservations")
    op.execute("DROP FUNCTION mark_stock_reservation_change()")
    op.drop_table("stock_reservation_changes")
