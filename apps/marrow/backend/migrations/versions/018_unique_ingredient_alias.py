"""unique_ingredient_alias

Revision ID: 018
Revises: 017
Create Date: 2026-07-09 00:00:00.000000

Adds a UNIQUE constraint on ``ingredient_aliases.alias`` so the lookup layer
cannot accumulate duplicate alias strings pointing at different canonicals.
The FK from ``alias`` → ``dietary_ingredients.canonical_name`` already
prevents orphans; this prevents silent overrides when a re-seed inserts the
same alias string twice.

Additive/data-preserving for clean databases. On a database with pre-existing
duplicate aliases the migration will fail — run the dedup query below first:

    DELETE FROM ingredient_aliases
    WHERE id NOT IN (
        SELECT MIN(id) FROM ingredient_aliases GROUP BY alias
    );
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ingredient_aliases") as batch_op:
        batch_op.create_unique_constraint("uq_ingredient_aliases_alias", ["alias"])


def downgrade() -> None:
    with op.batch_alter_table("ingredient_aliases") as batch_op:
        batch_op.drop_constraint("uq_ingredient_aliases_alias", type_="unique")
