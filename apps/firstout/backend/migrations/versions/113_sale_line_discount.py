"""Keep the line discount on invoice and sales order lines; warehouse may discount.

Firstout ADR 0001: a document stores the list unit price and the discount %, not a
discounted unit. Nullable columns only: rows written before this release keep NULL, which
readers treat as "the unit is already net" (P-020: the previous release ignores them).

ADR 0002: the built-in warehouse role gains till.discount, which replaces the quote role-slug
check. Custom roles are untouched. role_permissions is under forced RLS, so the grant loops
teams with app.tenant_id set. Startup role seeding adds the same key; this keeps the window
between migrate and boot, and inactive teams, consistent.

Revision ID: 113_sale_line_discount
Revises: 112_sale_line_unit_cost
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "113_sale_line_discount"
down_revision = "112_sale_line_unit_cost"
branch_labels = None
depends_on = None

_TABLES = ("invoice_lines", "sales_order_lines")


def _warehouse_discount(statement: str) -> None:
    op.execute(f"""DO $$
    DECLARE team uuid;
    BEGIN
        -- Filter by team as well: without forced RLS the policy does not narrow rows.
        FOR team IN SELECT id FROM teams LOOP
            PERFORM set_config('app.tenant_id', team::text, true);
            {statement}
        END LOOP;
        PERFORM set_config('app.tenant_id', '', true);
    END $$""")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True))
    _warehouse_discount(
        "INSERT INTO role_permissions (team_id, role_id, key) "
        "SELECT team_id, id, 'till.discount' FROM roles "
        "WHERE team_id = team AND slug = 'warehouse' AND is_system "
        "ON CONFLICT DO NOTHING;"
    )


def downgrade() -> None:
    _warehouse_discount(
        "DELETE FROM role_permissions WHERE team_id = team AND key = 'till.discount' "
        "AND role_id IN (SELECT id FROM roles "
        "WHERE team_id = team AND slug = 'warehouse' AND is_system);"
    )
    for table in _TABLES:
        op.drop_column(table, "discount_percent")
