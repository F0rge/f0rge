from __future__ import annotations

COPY_USER_CATALOG_FROM_REFERENCE_SQL = """
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
        user_id,
        canonical_name,
        category,
        histamine_score,
        fodmap_oligos,
        fodmap_fructose,
        fodmap_polyols,
        fodmap_lactose,
        contains_gluten,
        contains_dairy,
        source,
        source_version,
        archived,
        created_at,
        updated_at
    )
    SELECT
        p_new_user_id,
        canonical_name,
        category,
        histamine_score,
        fodmap_oligos,
        fodmap_fructose,
        fodmap_polyols,
        fodmap_lactose,
        contains_gluten,
        contains_dairy,
        source,
        source_version,
        archived,
        created_at,
        updated_at
    FROM dietary_ingredients
    WHERE user_id = p_ref_user_id
    ON CONFLICT (user_id, canonical_name) DO NOTHING;

    INSERT INTO ingredient_aliases (user_id, alias, canonical_name, language, created_at)
    SELECT p_new_user_id, alias, canonical_name, language, COALESCE(created_at, now())
    FROM ingredient_aliases
    WHERE user_id = p_ref_user_id
    ON CONFLICT (user_id, alias) DO NOTHING;

    INSERT INTO lab_marker_catalog (
        user_id,
        canonical_name,
        display_name,
        common_units,
        description,
        created_at
    )
    SELECT
        p_new_user_id,
        canonical_name,
        display_name,
        common_units,
        description,
        created_at
    FROM lab_marker_catalog
    WHERE user_id = p_ref_user_id
    ON CONFLICT (user_id, canonical_name) DO NOTHING;

    INSERT INTO lab_marker_aliases (user_id, catalog_id, alias, language, created_at)
    SELECT
        p_new_user_id,
        new_cat.id,
        src_alias.alias,
        src_alias.language,
        COALESCE(src_alias.created_at, now())
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
