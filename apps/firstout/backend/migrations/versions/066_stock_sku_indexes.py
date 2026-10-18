"""Add sku_id indexes on stock tables when none already lead with sku_id.

Revision ID: 066_stock_sku_indexes
Revises: 065_cin7_followup

sku_stock.sku_id is already unique. location_stock and bin_stock already have
ix_*_sku_id from migrations 005 and 029, and their unique constraints also lead
with sku_id. This revision only creates a named index when a table has no
index whose first column is sku_id. Downgrade drops ix_sku_stock_sku_id when
this revision created that non-unique index. It leaves the location and bin
indexes in place because 005 and 029 own those names.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "066_stock_sku_indexes"
down_revision: Union[str, Sequence[str], None] = "065_cin7_followup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES: tuple[tuple[str, str], ...] = (
    ("sku_stock", "ix_sku_stock_sku_id"),
    ("location_stock", "ix_location_stock_sku_id"),
    ("bin_stock", "ix_bin_stock_sku_id"),
)


def has_leading_sku_id_index(connection: sa.Connection, table: str) -> bool:
    inspector = sa.inspect(connection)
    for index in inspector.get_indexes(table):
        columns = index.get("column_names") or []
        if columns and columns[0] == "sku_id":
            return True
    for constraint in inspector.get_unique_constraints(table):
        columns = constraint.get("column_names") or []
        if columns and columns[0] == "sku_id":
            return True
    return False


def ensure_sku_id_index(connection: sa.Connection, table: str, index_name: str) -> None:
    if has_leading_sku_id_index(connection, table):
        return
    connection.execute(sa.text(f'CREATE INDEX "{index_name}" ON "{table}" (sku_id)'))


def upgrade() -> None:
    bind = op.get_bind()
    for table, index_name in _INDEXES:
        ensure_sku_id_index(bind, table, index_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("sku_stock"):
        if index["name"] == "ix_sku_stock_sku_id" and not index.get("unique"):
            op.drop_index("ix_sku_stock_sku_id", table_name="sku_stock")
            return
