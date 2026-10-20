"""Grant sales.quotes to the warehouse preset.

Revision ID: 069_warehouse_sales_quotes
Revises: 068_quote_line_discount

Existing databases already have the warehouse role from 033. New installs
pick the key up from ROLE_PRESETS when 033 runs; this insert is a no-op then.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "069_warehouse_sales_quotes"
down_revision: Union[str, Sequence[str], None] = "068_quote_line_discount"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO role_permissions (role_id, key) "
        "SELECT id, 'sales.quotes' FROM roles WHERE slug = 'warehouse' "
        "ON CONFLICT (role_id, key) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE key = 'sales.quotes' "
        "AND role_id IN (SELECT id FROM roles WHERE slug = 'warehouse')"
    )
