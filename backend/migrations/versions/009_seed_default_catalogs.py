"""seed_default_catalogs

Revision ID: 009
Revises: 008
Create Date: 2026-07-03 00:00:00.000000

Moves the default supplement_catalog and symptom_catalog rows out of the
app lifespan hook (app/main.py:_seed_supplement_catalog / _seed_symptom_catalog,
which re-ran a SELECT count() on every boot) and into a migration, matching
the pattern already established for diet_tag_catalog in 007.

Idempotent via ``ON CONFLICT (key) DO NOTHING`` — the same idiom migration
006 uses to seed built-in trackers. Both prod and dev already have these rows
(inserted by the old boot-time code), so this migration is a no-op there;
it only matters for a fresh database built straight from the migration chain.

Row values are copied verbatim from the DEFAULT_SUPPLEMENTS / DEFAULT_SYMPTOMS
lists that used to live in app/main.py, now in app/seed_data.py (imported
here as plain data — no ORM model import, per the migration-seed convention).

Downgrade is a no-op: these rows may have been edited (relabeled, reordered,
archived) by the user since they were seeded, and there's no reliable way to
tell a user edit from an untouched seed row. Deleting on downgrade risks
destroying real data, so we leave the rows in place.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.seed_data import DEFAULT_SUPPLEMENTS, DEFAULT_SYMPTOMS

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _values_clause(rows: list[tuple[str, str]]) -> str:
    """Render (key, label) tuples as a SQL VALUES list with literal strings.

    Seed values are fixed constants defined in app/seed_data.py, not user
    input, so string-formatting them into the statement (rather than binding
    params) is safe and matches the literal-VALUES style migration 006 uses.
    """
    lines = []
    for sort_order, (key, label) in enumerate(rows):
        key_sql = key.replace("'", "''")
        label_sql = label.replace("'", "''")
        lines.append(f"('{key_sql}', '{label_sql}', {sort_order}, false, now(), now())")
    return ",\n                ".join(lines)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO supplement_catalog (key, label, sort_order, archived, created_at, updated_at)
            VALUES
                {_values_clause(DEFAULT_SUPPLEMENTS)}
            ON CONFLICT (key) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO symptom_catalog (key, label, sort_order, archived, created_at, updated_at)
            VALUES
                {_values_clause(DEFAULT_SYMPTOMS)}
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """No-op. Seed rows may carry user edits (relabels, reorders, archives)
    that can't be distinguished from untouched seed data — deleting them
    here would risk destroying real data instead of undoing a migration."""
    pass
