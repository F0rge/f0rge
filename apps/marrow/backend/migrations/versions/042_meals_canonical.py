"""meals canonical entity for shared meal analysis

Revision ID: 042
Revises: 041
Create Date: 2026-07-12 00:00:00.000000

Introduce ``meals`` as the canonical food event; ``photos`` become entry
placements pointing at a shared ``meal_id``. ``photo_analyses`` are scoped
one-per-meal so tagged recipients read the tagger's analysis without cloning.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.sql.social_rls import MEALS_RLS_STATEMENTS, PHOTO_ANALYSES_MEAL_RLS_STATEMENTS
from f0rge_db.rls import migration_bypass

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("meal_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meals_owner_user_id", "meals", ["owner_user_id"])

    op.add_column("photos", sa.Column("meal_id", sa.Integer(), nullable=True))
    op.create_index("ix_photos_meal_id", "photos", ["meal_id"])

    bind = op.get_bind()
    with migration_bypass(bind, ["photos"]):
        bind.execute(
            sa.text(
                """
                DO $$
                DECLARE
                  r RECORD;
                  new_meal_id INT;
                  src_meal_id INT;
                BEGIN
                  FOR r IN SELECT id, user_id, filename, label, original_filename,
                                  meal_time, created_at, source_photo_id
                           FROM photos ORDER BY id
                  LOOP
                    IF r.source_photo_id IS NULL THEN
                      INSERT INTO meals (
                        owner_user_id, filename, label, original_filename, meal_time, created_at
                      ) VALUES (
                        r.user_id, r.filename, r.label, r.original_filename, r.meal_time, r.created_at
                      ) RETURNING id INTO new_meal_id;
                      UPDATE photos SET meal_id = new_meal_id WHERE id = r.id;
                    ELSE
                      SELECT meal_id INTO src_meal_id FROM photos WHERE id = r.source_photo_id;
                      IF src_meal_id IS NULL THEN
                        RAISE EXCEPTION 'source photo % has no meal_id when backfilling photo %',
                          r.source_photo_id, r.id;
                      END IF;
                      UPDATE photos SET meal_id = src_meal_id WHERE id = r.id;
                    END IF;
                  END LOOP;
                END $$;
                """
            )
        )

    op.alter_column("photos", "meal_id", nullable=False)
    op.create_foreign_key(
        "photos_meal_id_fkey",
        "photos",
        "meals",
        ["meal_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column("photo_analyses", sa.Column("meal_id", sa.Integer(), nullable=True))

    with migration_bypass(bind, ["photo_analyses"]):
        bind.execute(
            sa.text(
                """
                UPDATE photo_analyses pa
                SET meal_id = p.meal_id
                FROM photos p
                WHERE p.id = pa.photo_id
                """
            )
        )

        bind.execute(
            sa.text(
                """
                DELETE FROM photo_analyses pa
                USING photos p
                WHERE p.id = pa.photo_id
                  AND p.source_photo_id IS NOT NULL
                  AND pa.meal_id IN (
                    SELECT meal_id FROM photo_analyses GROUP BY meal_id HAVING COUNT(*) > 1
                  )
                """
            )
        )

    op.alter_column("photo_analyses", "meal_id", nullable=False)
    op.create_unique_constraint("uq_photo_analyses_meal_id", "photo_analyses", ["meal_id"])
    op.create_foreign_key(
        "photo_analyses_meal_id_fkey",
        "photo_analyses",
        "meals",
        ["meal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_photo_analyses_meal_id", "photo_analyses", ["meal_id"])

    op.drop_constraint("photo_analyses_photo_id_key", "photo_analyses", type_="unique")
    op.drop_constraint("photo_analyses_photo_id_fkey", "photo_analyses", type_="foreignkey")
    op.create_foreign_key(
        "photo_analyses_photo_id_fkey",
        "photo_analyses",
        "photos",
        ["photo_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("photo_analyses", "photo_id", nullable=True)

    op.add_column("meal_tags", sa.Column("source_meal_id", sa.Integer(), nullable=True))

    with migration_bypass(bind, ["meal_tags"]):
        bind.execute(
            sa.text(
                """
                UPDATE meal_tags mt
                SET source_meal_id = p.meal_id
                FROM photos p
                WHERE p.id = mt.source_photo_id
                """
            )
        )

    op.alter_column("meal_tags", "source_meal_id", nullable=False)
    op.create_foreign_key(
        "meal_tags_source_meal_id_fkey",
        "meal_tags",
        "meals",
        ["source_meal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_meal_tags_source_meal", "meal_tags", ["source_meal_id"])

    for stmt in MEALS_RLS_STATEMENTS:
        op.execute(sa.text(stmt))
    for stmt in PHOTO_ANALYSES_MEAL_RLS_STATEMENTS:
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS photo_ingredients_meal_participant_delete ON photo_ingredients"
        )
    )
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS photo_ingredients_meal_participant_update ON photo_ingredients"
        )
    )
    op.execute(
        sa.text(
            "DROP POLICY IF EXISTS photo_ingredients_meal_participant_select ON photo_ingredients"
        )
    )
    op.execute(
        sa.text("DROP POLICY IF EXISTS photo_analyses_meal_participant_delete ON photo_analyses")
    )
    op.execute(
        sa.text("DROP POLICY IF EXISTS photo_analyses_meal_participant_update ON photo_analyses")
    )
    op.execute(
        sa.text("DROP POLICY IF EXISTS photo_analyses_meal_participant_select ON photo_analyses")
    )
    op.execute(sa.text("DROP POLICY IF EXISTS meals_participant_select ON meals"))
    op.execute(sa.text("DROP POLICY IF EXISTS meals_owner ON meals"))
    op.execute(sa.text("ALTER TABLE meals DISABLE ROW LEVEL SECURITY"))

    op.drop_index("ix_meal_tags_source_meal", table_name="meal_tags")
    op.drop_constraint("meal_tags_source_meal_id_fkey", "meal_tags", type_="foreignkey")
    op.drop_column("meal_tags", "source_meal_id")

    op.drop_constraint("photo_analyses_photo_id_fkey", "photo_analyses", type_="foreignkey")
    op.execute(
        sa.text(
            """
            UPDATE photo_analyses SET photo_id = (
              SELECT id FROM photos WHERE photos.meal_id = photo_analyses.meal_id
              ORDER BY source_photo_id NULLS FIRST, id LIMIT 1
            )
            WHERE photo_id IS NULL
            """
        )
    )
    op.alter_column("photo_analyses", "photo_id", nullable=False)
    op.create_foreign_key(
        "photo_analyses_photo_id_fkey",
        "photo_analyses",
        "photos",
        ["photo_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("photo_analyses_photo_id_key", "photo_analyses", ["photo_id"])

    op.drop_index("ix_photo_analyses_meal_id", table_name="photo_analyses")
    op.drop_constraint("photo_analyses_meal_id_fkey", "photo_analyses", type_="foreignkey")
    op.drop_constraint("uq_photo_analyses_meal_id", "photo_analyses", type_="unique")
    op.drop_column("photo_analyses", "meal_id")

    op.drop_constraint("photos_meal_id_fkey", "photos", type_="foreignkey")
    op.drop_index("ix_photos_meal_id", table_name="photos")
    op.drop_column("photos", "meal_id")

    op.drop_index("ix_meals_owner_user_id", table_name="meals")
    op.drop_table("meals")
