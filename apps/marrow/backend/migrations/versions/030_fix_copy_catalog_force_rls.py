"""fix_copy_catalog_force_rls

Revision ID: 030
Revises: 029
Create Date: 2026-07-11 14:00:00.000000

Recreate copy_user_catalog_from_reference with SET row_security = off so the
SECURITY DEFINER function can read the reference user's rows when FORCE RLS is
enabled (prod). Backfills users marked provisioned but missing ingredients.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _reference_user_id() -> str:
    return os.environ.get("DEFAULT_STORAGE_USER_ID", "00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    ref_user_id = _reference_user_id()
    op.execute(sa.text(COPY_USER_CATALOG_FROM_REFERENCE_SQL))
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE
                u record;
            BEGIN
                FOR u IN
                    SELECT id FROM users
                    WHERE id != '{ref_user_id}'::uuid
                      AND infrastructure_provisioned_at IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM dietary_ingredients di
                          WHERE di.user_id = users.id
                          LIMIT 1
                      )
                LOOP
                    PERFORM copy_user_catalog_from_reference(u.id, '{ref_user_id}'::uuid);
                END LOOP;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    # Restore the pre-fix function body (without row_security = off).
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION copy_user_catalog_from_reference(
                p_new_user_id uuid,
                p_ref_user_id uuid
            ) RETURNS void
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = public
            AS $$
            BEGIN
                INSERT INTO dietary_ingredients (
                    user_id, canonical_name, category, histamine_score,
                    fodmap_oligos, fodmap_fructose, fodmap_polyols, fodmap_lactose,
                    contains_gluten, contains_dairy, source, source_version,
                    archived, created_at, updated_at
                )
                SELECT
                    p_new_user_id, canonical_name, category, histamine_score,
                    fodmap_oligos, fodmap_fructose, fodmap_polyols, fodmap_lactose,
                    contains_gluten, contains_dairy, source, source_version,
                    archived, created_at, updated_at
                FROM dietary_ingredients
                WHERE user_id = p_ref_user_id
                ON CONFLICT (user_id, canonical_name) DO NOTHING;

                INSERT INTO ingredient_aliases (user_id, alias, canonical_name, language)
                SELECT p_new_user_id, alias, canonical_name, language
                FROM ingredient_aliases
                WHERE user_id = p_ref_user_id
                ON CONFLICT (user_id, alias) DO NOTHING;

                INSERT INTO lab_marker_catalog (
                    user_id, canonical_name, display_name,
                    common_units, description, created_at
                )
                SELECT
                    p_new_user_id, canonical_name, display_name,
                    common_units, description, created_at
                FROM lab_marker_catalog
                WHERE user_id = p_ref_user_id
                ON CONFLICT (user_id, canonical_name) DO NOTHING;

                INSERT INTO lab_marker_aliases (user_id, catalog_id, alias, language)
                SELECT
                    p_new_user_id, new_cat.id, src_alias.alias, src_alias.language
                FROM lab_marker_aliases src_alias
                JOIN lab_marker_catalog src_cat
                    ON src_cat.id = src_alias.catalog_id
                    AND src_cat.user_id = p_ref_user_id
                JOIN lab_marker_catalog new_cat
                    ON new_cat.canonical_name = src_cat.canonical_name
                    AND new_cat.user_id = p_new_user_id
                ON CONFLICT (user_id, alias) DO NOTHING;
            END;
            $$;
            """
        )
    )
