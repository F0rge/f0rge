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

_CREATED_AT_TABLES: tuple[tuple[str, str | None], ...] = (
    ("ingredient_aliases", None),
    ("lab_marker_aliases", None),
    ("lab_markers", None),
    ("tracker_log", "updated_at"),
    ("treatment_log", "updated_at"),
)


def upgrade() -> None:
    bind = op.get_bind()

    for table, backfill_column in _CREATED_AT_TABLES:
        op.add_column(table, sa.Column("created_at", sa.DateTime(), nullable=True))
        if backfill_column is None:
            bind.execute(sa.text(f"UPDATE {table} SET created_at = now() WHERE created_at IS NULL"))
        else:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET created_at = {backfill_column} WHERE created_at IS NULL"
                )
            )
        op.alter_column(table, "created_at", nullable=False)

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

    for table, _ in reversed(_CREATED_AT_TABLES):
        op.drop_column(table, "created_at")
