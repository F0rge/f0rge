"""model_hygiene

Revision ID: 033
Revises: 032
Create Date: 2026-07-12 00:00:00.000000

Model-layer hygiene from guidelines audit #287:

- Add ``created_at`` to alias/marker/log tables missing it
- Convert ``embedding_queue`` timestamp columns from TIMESTAMPTZ to tz-naive UTC
  (``enqueued_at`` is the semantic create timestamp for this table)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_CREATED_AT_DEFAULT_TABLES: tuple[str, ...] = (
    "ingredient_aliases",
    "lab_marker_aliases",
    "lab_markers",
)

_CREATED_AT_FROM_COLUMN: tuple[tuple[str, str], ...] = (
    ("tracker_log", "updated_at"),
    ("treatment_log", "updated_at"),
)


def _backfill_created_at_from_column(bind: sa.Connection, table: str, source_column: str) -> None:
    """Backfill ``created_at`` from another column under FORCE RLS.

      Postgres rejects ``DEFAULT updated_at`` (column refs in DEFAULT), and a
    blind ``UPDATE`` as ``schema_admin`` touches 0 rows under tenant policies.
      Loop per user via ``set_config('app.user_id', ...)`` — same as migration 031.
    """
    op.add_column(
        table,
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    user_ids = [r[0] for r in bind.execute(sa.text("SELECT id::text FROM users")).fetchall()]
    for uid in user_ids:
        bind.execute(sa.text("SELECT set_config('app.user_id', :uid, true)"), {"uid": uid})
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET created_at = {source_column}
                WHERE created_at IS NULL
                """
            )
        )
    op.alter_column(table, "created_at", nullable=False)


def upgrade() -> None:
    bind = op.get_bind()

    # DDL ADD COLUMN ... DEFAULT backfills existing rows without going through RLS UPDATE.
    for table in _CREATED_AT_DEFAULT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.alter_column(table, "created_at", server_default=None)

    for table, source_column in _CREATED_AT_FROM_COLUMN:
        _backfill_created_at_from_column(bind, table, source_column)

    bind.execute(
        sa.text(
            """
            ALTER TABLE embedding_queue
            ALTER COLUMN enqueued_at TYPE TIMESTAMP WITHOUT TIME ZONE
            USING (enqueued_at AT TIME ZONE 'UTC')
            """
        )
    )
    bind.execute(
        sa.text(
            """
            ALTER TABLE embedding_queue
            ALTER COLUMN last_attempt_at TYPE TIMESTAMP WITHOUT TIME ZONE
            USING (
                CASE
                    WHEN last_attempt_at IS NULL THEN NULL
                    ELSE last_attempt_at AT TIME ZONE 'UTC'
                END
            )
            """
        )
    )

    # Alias tables now require created_at; refresh the signup copy function.
    op.execute(sa.text(COPY_USER_CATALOG_FROM_REFERENCE_SQL))


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            ALTER TABLE embedding_queue
            ALTER COLUMN last_attempt_at TYPE TIMESTAMP WITH TIME ZONE
            USING last_attempt_at AT TIME ZONE 'UTC'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            ALTER TABLE embedding_queue
            ALTER COLUMN enqueued_at TYPE TIMESTAMP WITH TIME ZONE
            USING enqueued_at AT TIME ZONE 'UTC'
            """
        )
    )

    for table, _ in reversed(_CREATED_AT_FROM_COLUMN):
        op.drop_column(table, "created_at")

    for table in reversed(_CREATED_AT_DEFAULT_TABLES):
        op.drop_column(table, "created_at")
