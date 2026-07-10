"""embedding_pipeline

Revision ID: f6a8b3c1d920
Revises: d4e7a1b2c903
Create Date: 2026-05-16 00:00:00.000000

Adds the embedding pipeline infrastructure:

1. ``embedding_queue`` table — a durable outbox that tracks every row-level
   change that needs to be (re-)embedded.  The worker process polls this table
   (or wakes via LISTEN/NOTIFY) and calls the embedding API, then writes the
   resulting vector to the ``embedding`` table.  Using a queue table rather
   than a direct API call inside the trigger keeps the write path fast and
   makes retries observable.

2. ``enqueue_embedding()`` trigger function — a single PL/pgSQL function
   shared by all four source triggers.  It inserts a row into
   ``embedding_queue`` and fires a ``pg_notify('embedding_queue', 'wake')``
   pulse so an idle worker can react immediately without polling.

3. Four AFTER triggers, one per watched source table, each scoped to the
   specific columns whose content feeds the embedding text:

   - ``entries``       — watches ``notes``
   - ``labs``          — watches ``raw_text``
   - ``treatments``    — watches ``name, dose, notes``
   - ``photo_analyses``— watches ``dish_name, raw_response``

   On DELETE the trigger captures ``OLD.id`` so the worker can tombstone the
   corresponding ``embedding`` rows.

Worker access: the main ``health`` Postgres user already owns all tables, so
no additional grants are needed for the worker.  The ``healthtracker_ro`` role
created in migration 004 must NOT be able to insert into ``embedding_queue`` —
that is enforced by the role's SELECT-only privileges.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a8b3c1d920"
down_revision: Union[str, None] = "d4e7a1b2c903"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. embedding_queue table
    # ------------------------------------------------------------------
    op.create_table(
        "embedding_queue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("source_table", sa.String(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('INSERT', 'UPDATE', 'DELETE')",
            name="embedding_queue_action_check",
        ),
    )

    # Partial index: only rows that still have attempts remaining need fast lookup.
    op.create_index(
        "ix_embedding_queue_enqueued",
        "embedding_queue",
        ["enqueued_at"],
        postgresql_where=sa.text("attempts < 5"),
    )

    # ------------------------------------------------------------------
    # 2. Shared trigger function
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_embedding() RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO embedding_queue (source_table, source_id, action)
                    VALUES (TG_TABLE_NAME, OLD.id, 'DELETE');
                ELSE
                    INSERT INTO embedding_queue (source_table, source_id, action)
                    VALUES (TG_TABLE_NAME, NEW.id, TG_OP);
                END IF;
                PERFORM pg_notify('embedding_queue', 'wake');
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # ------------------------------------------------------------------
    # 3. Four AFTER triggers, one per source table
    # ------------------------------------------------------------------

    # entries — only re-embed when notes changes.
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_entries_embedding
            AFTER INSERT OR DELETE OR UPDATE OF notes
            ON entries
            FOR EACH ROW EXECUTE FUNCTION enqueue_embedding();
            """
        )
    )

    # labs — only re-embed when raw_text changes.
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_labs_embedding
            AFTER INSERT OR DELETE OR UPDATE OF raw_text
            ON labs
            FOR EACH ROW EXECUTE FUNCTION enqueue_embedding();
            """
        )
    )

    # treatments — re-embed on any change to the fields that compose
    # the semantic description of a treatment.  The treatments table has no
    # frequency column; watched columns are name, dose, notes.
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_treatments_embedding
            AFTER INSERT OR DELETE OR UPDATE OF name, dose, notes
            ON treatments
            FOR EACH ROW EXECUTE FUNCTION enqueue_embedding();
            """
        )
    )

    # photo_analyses — re-embed when the dish name or raw LLM response changes.
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_photo_analyses_embedding
            AFTER INSERT OR DELETE OR UPDATE OF dish_name, raw_response
            ON photo_analyses
            FOR EACH ROW EXECUTE FUNCTION enqueue_embedding();
            """
        )
    )

    # The main ``health`` user already owns all tables — no grants needed for the
    # worker. ``healthtracker_ro`` cannot INSERT into embedding_queue because
    # migration 004 only granted it SELECT.


def downgrade() -> None:
    # Drop triggers first (they depend on the function).
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_photo_analyses_embedding ON photo_analyses"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_treatments_embedding ON treatments"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_labs_embedding ON labs"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_entries_embedding ON entries"))

    # Drop the shared function.
    op.execute(sa.text("DROP FUNCTION IF EXISTS enqueue_embedding()"))

    # Drop the queue table (index is dropped automatically with the table).
    op.drop_index("ix_embedding_queue_enqueued", table_name="embedding_queue")
    op.drop_table("embedding_queue")
