"""guard_embedding_trigger_on_user_delete

Revision ID: 025
Revises: 024
Create Date: 2026-07-10 00:00:00.000000

``DELETE FROM users`` cascades into entries/labs/treatments/photo_analyses,
whose AFTER DELETE trigger (``enqueue_embedding``, migration 005/020) inserts
an ``embedding_queue`` row referencing the user mid-delete. The FK check no
longer finds the users row, so the whole account deletion rolls back with a
ForeignKeyViolationError (#229). A user being deleted has their queue and
embedding rows removed by the same cascade, so no DELETE job is needed:
skip the enqueue when the users row is already gone.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_embedding() RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    SELECT OLD.user_id, TG_TABLE_NAME, OLD.id, 'DELETE'
                    WHERE EXISTS (SELECT 1 FROM users WHERE id = OLD.user_id);
                ELSE
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    VALUES (NEW.user_id, TG_TABLE_NAME, NEW.id, TG_OP);
                END IF;
                PERFORM pg_notify('embedding_queue', 'wake');
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_embedding() RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    VALUES (OLD.user_id, TG_TABLE_NAME, OLD.id, 'DELETE');
                ELSE
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    VALUES (NEW.user_id, TG_TABLE_NAME, NEW.id, TG_OP);
                END IF;
                PERFORM pg_notify('embedding_queue', 'wake');
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
