"""expand_catalogs_and_split_vitamin_d_k2

Revision ID: 011
Revises: 010
Create Date: 2026-07-04 00:00:00.000000

Two independent changes, bundled because they touch the same two tables:

1. Split the combined ``vitamin_d_k2`` supplement into two separate active
   entries (``vitamin_d``, ``vitamin_k2``), and archive the combined entry.
   ``vitamin_d_k2`` is NOT deleted -- historical ``entries.supplements``
   strings from past days still reference that key, and its label must stay
   in ``supplement_catalog`` for the (separately tracked, pre-existing) issue
   where the history view renders raw keys when a lookup misses. Deleting the
   row would turn that existing display bug into a hard lookup failure.

2. Bulk-seed ~115 additional supplements and ~103 additional medications
   (generic names, one entry per commonly-recognized item -- not per salt/
   ester variant) so the user can search and activate whatever they actually
   take via /customize/catalogs, instead of us adding items one at a time.

   These bulk rows are seeded ``archived = true``. The daily check-in picker
   only shows active (non-archived) catalog items -- seeding 200+ rows as
   active would flood that picker for every single day going forward. Setting
   them archived makes them discoverable via the catalog search / manage
   screen (which lists archived items too) without changing the daily UX at
   all. The user ticks "unarchive" on whatever they actually take.

Idempotent, matching migration 009's approach: every INSERT uses
``postgresql.insert(...).on_conflict_do_nothing(index_elements=["key"])``, so
re-running (or a fresh ``alembic upgrade head``) never duplicates rows and
never modifies a row that already exists -- including one a user has since
relabeled, reordered, or unarchived themselves. The ONLY existing-row
modification in this migration is the single, explicit ``vitamin_d_k2``
archive UPDATE below; every other row this migration touches is a brand-new
key that cannot yet exist on any real database.

Row data lives in app/seed_data.py (SPLIT_VITAMIN_D_K2, BULK_SUPPLEMENTS,
BULK_MEDICATIONS) -- imported as plain data, no ORM model import, per the
migration-seed convention established in 007/009/010. These three new
constants are NOT read by any other migration, so they can grow over time
without affecting migrations 009/010's frozen historical behaviour (which
read the separate, untouched DEFAULT_SUPPLEMENTS/DEFAULT_MEDICATIONS lists).

Downgrade reverses cleanly: delete every bulk-seeded row plus vitamin_d/
vitamin_k2 by key, then un-archive vitamin_d_k2. Safe because every row this
migration inserts uses a key that could not have existed before it ran (no
"was this a user edit?" ambiguity like migration 009's downgrade has).
"""

from __future__ import annotations

import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.seed_data import BULK_MEDICATIONS, BULK_SUPPLEMENTS, SPLIT_VITAMIN_D_K2

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _catalog_table(name: str) -> sa.Table:
    """Lightweight sa.table() reference -- never import the ORM model here,
    migrations must be frozen-in-time (see migration_seed_pattern memory)."""
    return sa.table(
        name,
        sa.column("key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("archived", sa.Boolean()),
        sa.column("first_used_at", sa.DateTime()),
        sa.column("last_used_at", sa.DateTime()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )


def _rows(
    pairs: list[tuple[str, str]], *, archived: bool, start_sort_order: int, now: datetime.datetime
) -> list[dict]:
    return [
        {
            "key": key,
            "label": label,
            "archived": archived,
            "first_used_at": None,
            "last_used_at": None,
            "sort_order": start_sort_order + i,
            "created_at": now,
            "updated_at": now,
        }
        for i, (key, label) in enumerate(pairs)
    ]


def _insert_on_conflict_do_nothing(table: sa.Table, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = postgresql.insert(table).values(rows).on_conflict_do_nothing(index_elements=["key"])
    op.execute(stmt)


def upgrade() -> None:
    now = datetime.datetime.utcnow()
    supplement_catalog = _catalog_table("supplement_catalog")
    medication_catalog = _catalog_table("medication_catalog")

    # --- Task B: split vitamin_d_k2 into two active entries ---
    # sort_order continues after the 9 rows seeded by migration 009
    # (DEFAULT_SUPPLEMENTS has 9 entries, positions 0-8).
    _insert_on_conflict_do_nothing(
        supplement_catalog,
        _rows(SPLIT_VITAMIN_D_K2, archived=False, start_sort_order=9, now=now),
    )
    op.execute(
        sa.text(
            "UPDATE supplement_catalog SET archived = true, updated_at = :now "
            "WHERE key = 'vitamin_d_k2'"
        ).bindparams(now=now)
    )

    # --- Task A: bulk-seed exhaustive supplement/medication reference data ---
    # sort_order continues after the split rows above (9 + 2 = 11).
    _insert_on_conflict_do_nothing(
        supplement_catalog,
        _rows(BULK_SUPPLEMENTS, archived=True, start_sort_order=11, now=now),
    )
    # DEFAULT_MEDICATIONS (migration 010) has 6 entries, positions 0-5.
    _insert_on_conflict_do_nothing(
        medication_catalog,
        _rows(BULK_MEDICATIONS, archived=True, start_sort_order=6, now=now),
    )


def downgrade() -> None:
    bulk_supplement_keys = [key for key, _ in BULK_SUPPLEMENTS] + [
        key for key, _ in SPLIT_VITAMIN_D_K2
    ]
    bulk_medication_keys = [key for key, _ in BULK_MEDICATIONS]

    op.execute(
        sa.text("DELETE FROM supplement_catalog WHERE key = ANY(:keys)").bindparams(
            sa.bindparam("keys", value=bulk_supplement_keys, type_=postgresql.ARRAY(sa.String()))
        )
    )
    op.execute(
        sa.text("DELETE FROM medication_catalog WHERE key = ANY(:keys)").bindparams(
            sa.bindparam("keys", value=bulk_medication_keys, type_=postgresql.ARRAY(sa.String()))
        )
    )
    op.execute(sa.text("UPDATE supplement_catalog SET archived = false WHERE key = 'vitamin_d_k2'"))
