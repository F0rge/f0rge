"""add_trackers

Revision ID: a1b2c3d4e506
Revises: f6a8b3c1d920
Create Date: 2026-05-23 00:00:00.000000

Adds two tables to support user-defined daily trackers:

1. ``tracker`` — definitions: name, kind (counter/binary), icon, unit,
   display order, archive flag, and an ``is_seed`` sentinel that marks the
   four built-in trackers that dual-write with the legacy ``entry.*`` columns.

2. ``tracker_log`` — one row per (tracker, date) holding the day's value.
   Composite PK ``(tracker_id, date)``; index on ``date`` for the "fetch all
   values for one day" query.

After creating the tables the migration:

* Inserts the 4 seed trackers (alcohol units, caffeine servings, sick, hot
  shower) using ``ON CONFLICT (name) DO NOTHING`` so re-running is safe.

* Backfills ``tracker_log`` from existing ``entries`` rows, skipping zeros for
  counter types (no point logging "0 alcohol units").  Uses
  ``ON CONFLICT (tracker_id, date) DO UPDATE SET value = EXCLUDED.value``
  for full idempotency.

Down-migration drops both new tables; the original ``entry.*`` columns are
untouched so the old form and history page keep working after a rollback.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e506"
down_revision: Union[str, None] = "f6a8b3c1d920"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. tracker table
    # ------------------------------------------------------------------
    op.create_table(
        "tracker",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", name="uq_tracker_name"),
        sa.CheckConstraint("kind IN ('counter', 'binary')", name="ck_tracker_kind"),
    )

    # ------------------------------------------------------------------
    # 2. tracker_log table
    # ------------------------------------------------------------------
    op.create_table(
        "tracker_log",
        sa.Column("tracker_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("tracker_id", "date", name="pk_tracker_log"),
        sa.ForeignKeyConstraint(
            ["tracker_id"],
            ["tracker.id"],
            ondelete="CASCADE",
            name="fk_tracker_log_tracker_id",
        ),
    )

    op.create_index("ix_tracker_log_date", "tracker_log", ["date"])

    # ------------------------------------------------------------------
    # 3. Seed the 4 built-in trackers
    #    ON CONFLICT DO NOTHING makes this idempotent on re-run.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO tracker (name, kind, icon, unit, position, archived, is_seed)
            VALUES
                ('Alcohol units',     'counter', 'wine',         'units',    0, false, true),
                ('Caffeine servings', 'counter', 'coffee',       'servings', 1, false, true),
                ('Sick',              'binary',  'thermometer',  NULL,       2, false, true),
                ('Hot shower',        'binary',  'droplets',     NULL,       3, false, true)
            ON CONFLICT (name) DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------
    # 4. Backfill tracker_log from existing entry rows
    #
    #    Rules:
    #    - alcohol_units: skip NULL and zero (no point logging 0).
    #    - caffeine_servings: skip NULL and zero.
    #    - sick: insert 1 when true, skip when false/NULL.
    #    - hot_shower: insert 1 when true, skip when false/NULL.
    #
    #    ON CONFLICT ... DO UPDATE makes repeated runs idempotent.
    #    Tracker ids are resolved via a subselect on (name, is_seed)
    #    so we are not coupled to any particular SERIAL value.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO tracker_log (tracker_id, date, value)
            SELECT
                (SELECT id FROM tracker WHERE name = 'Alcohol units' AND is_seed = true),
                e.date,
                e.alcohol_units
            FROM entries e
            WHERE e.alcohol_units IS NOT NULL
              AND e.alcohol_units > 0
            ON CONFLICT (tracker_id, date)
            DO UPDATE SET value = EXCLUDED.value
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tracker_log (tracker_id, date, value)
            SELECT
                (SELECT id FROM tracker WHERE name = 'Caffeine servings' AND is_seed = true),
                e.date,
                e.caffeine_servings
            FROM entries e
            WHERE e.caffeine_servings IS NOT NULL
              AND e.caffeine_servings > 0
            ON CONFLICT (tracker_id, date)
            DO UPDATE SET value = EXCLUDED.value
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tracker_log (tracker_id, date, value)
            SELECT
                (SELECT id FROM tracker WHERE name = 'Sick' AND is_seed = true),
                e.date,
                1
            FROM entries e
            WHERE e.sick = true
            ON CONFLICT (tracker_id, date)
            DO UPDATE SET value = EXCLUDED.value
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tracker_log (tracker_id, date, value)
            SELECT
                (SELECT id FROM tracker WHERE name = 'Hot shower' AND is_seed = true),
                e.date,
                1
            FROM entries e
            WHERE e.hot_shower = true
            ON CONFLICT (tracker_id, date)
            DO UPDATE SET value = EXCLUDED.value
            """
        )
    )


def downgrade() -> None:
    # tracker_log must go first — it holds the FK reference to tracker.
    op.drop_index("ix_tracker_log_date", table_name="tracker_log")
    op.drop_table("tracker_log")
    op.drop_table("tracker")
