"""provisioner_copy_policy

Revision ID: 032
Revises: 031
Create Date: 2026-07-11 15:00:00.000000

Add a `provisioner` service-role RLS policy on the four catalog tables the
signup copy touches, and recreate copy_user_catalog_from_reference WITHOUT
``SET row_security = off``.

Migration 030 assumed ``row_security = off`` bypasses RLS, but it only does for a
BYPASSRLS/superuser function owner. On prod (f0rge-db) the owner ``schema_admin``
is neither, and the catalog tables use FORCE ROW LEVEL SECURITY, so the copy
raised InsufficientPrivilege and aborted signup. The service-role policy mirrors
the existing ``worker_queue`` / ``mcp_auth_lookup`` pattern: the caller sets
``app.service_role = 'provisioner'`` around the copy (see UserProvisioningCRUD),
which authorizes the cross-tenant reads/writes without any role attribute.

``schema_admin`` owns these tables (migration 027 ran their FORCE RLS as
schema_admin), so CREATE POLICY here succeeds.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_CATALOG_TABLES: tuple[str, ...] = (
    "dietary_ingredients",
    "ingredient_aliases",
    "lab_marker_catalog",
    "lab_marker_aliases",
)

# Prior prod function body (WITH row_security = off) — restored on downgrade.
_PREV_COPY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION copy_user_catalog_from_reference(
    p_new_user_id uuid,
    p_ref_user_id uuid
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
SET row_security = off
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


def upgrade() -> None:
    for table in _CATALOG_TABLES:
        op.execute(
            sa.text(
                f"""
                CREATE POLICY provisioner_copy ON {table}
                    FOR ALL
                    USING (current_setting('app.service_role', true) = 'provisioner')
                    WITH CHECK (current_setting('app.service_role', true) = 'provisioner')
                """
            )
        )
    # Recreate the function without `SET row_security = off`; it now relies on
    # the caller setting app.service_role='provisioner' + the policy above.
    op.execute(sa.text(COPY_USER_CATALOG_FROM_REFERENCE_SQL))


def downgrade() -> None:
    op.execute(sa.text(_PREV_COPY_FUNCTION_SQL))
    for table in _CATALOG_TABLES:
        op.execute(sa.text(f"DROP POLICY IF EXISTS provisioner_copy ON {table}"))
