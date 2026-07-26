from __future__ import annotations

import sqlalchemy as sa
from f0rge_db.rls import create_service_role_policy, enable_tenant_isolation
from app.sql.social_functions import (
    CREATE_NOTIFICATION_SQL,
    IS_GROUP_MEMBER_SQL,
    IS_GROUP_OWNER_SQL,
    SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL,
    SOCIAL_LOOKUP_GROUPS_POLICY_SQL,
    SOCIAL_NOTIFIER_POLICY_SQL,
)
from app.sql.social_rls import (
    CONNECTIONS_RLS_STATEMENTS,
    GROUP_MEMBERS_RLS_STATEMENTS,
    GROUPS_RLS_STATEMENTS,
    MEALS_RLS_STATEMENTS,
    MEAL_TAGS_RLS_STATEMENTS,
    NOTIFICATIONS_RLS_STATEMENTS,
    PHOTO_ANALYSES_MEAL_RLS_STATEMENTS,
)
from sqlalchemy.ext.asyncio import AsyncConnection

# Live bootstrap list (runtime + tests). Migrations 020/021 hold their own
# frozen copies and do NOT import this; new user-owned tables are appended
# here and get their RLS DDL inline in their own migration (cf. 045).
USER_OWNED_TABLES: tuple[str, ...] = (
    "entries",
    "photos",
    "photo_analyses",
    "photo_ingredients",
    "tracker",
    "tracker_log",
    "treatments",
    "treatment_log",
    "labs",
    "lab_markers",
    "health_metrics",
    "weather_readings",
    "embedding",
    "embedding_queue",
    "meal_analysis_queue",
    "user_settings",
    "diet_tag_catalog",
    "supplement_catalog",
    "symptom_catalog",
    "medication_catalog",
    "lab_marker_catalog",
    "lab_marker_aliases",
    "dietary_ingredients",
    "ingredient_aliases",
    "photo_diet_tags",
    "device_tokens",
)

# The four catalog tables the signup copy touches (mirrors migration 032).
PROVISIONER_COPY_TABLES: tuple[str, ...] = (
    "dietary_ingredients",
    "ingredient_aliases",
    "lab_marker_catalog",
    "lab_marker_aliases",
)


async def enable_row_level_security(conn: AsyncConnection) -> None:
    """Apply tenant RLS policies (mirrors migrations 021 + 032 + 045)."""
    await enable_tenant_isolation(conn, USER_OWNED_TABLES)
    await create_service_role_policy(
        conn,
        name="mcp_auth_lookup",
        tables=("user_settings",),
        role="mcp_auth",
        command="SELECT",
    )
    await create_service_role_policy(
        conn,
        name="worker_queue",
        tables=("embedding_queue", "meal_analysis_queue"),
        role="worker",
    )
    # Mirrors migration 047: device registration deletes another user's stale
    # row for the same token (phone changed owners) under this role. The
    # takeover path only deletes, but the policy must stay ALL: a DELETE whose
    # WHERE references table columns also needs the row visible via a SELECT
    # or ALL policy, so a DELETE-only policy matches zero cross-tenant rows.
    await create_service_role_policy(
        conn,
        name="device_registrar",
        tables=("device_tokens",),
        role="device_registrar",
    )
    # Mirrors migration 032: lets copy_user_catalog_from_reference cross tenants
    # under FORCE RLS when the caller sets app.service_role='provisioner'.
    await create_service_role_policy(
        conn,
        name="provisioner_copy",
        tables=PROVISIONER_COPY_TABLES,
        role="provisioner",
    )


async def enable_social_security(conn: AsyncConnection) -> None:
    """Mirror social-layer migration DDL for test schema bootstrap."""
    for stmt in NOTIFICATIONS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
    await conn.execute(sa.text(SOCIAL_NOTIFIER_POLICY_SQL))
    await conn.execute(sa.text(CREATE_NOTIFICATION_SQL))

    for stmt in CONNECTIONS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))

    await conn.execute(sa.text(SOCIAL_LOOKUP_GROUPS_POLICY_SQL))
    await conn.execute(sa.text(SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL))
    await conn.execute(sa.text(IS_GROUP_MEMBER_SQL))
    await conn.execute(sa.text(IS_GROUP_OWNER_SQL))

    for stmt in GROUPS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
    for stmt in GROUP_MEMBERS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
    for stmt in MEAL_TAGS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
    for stmt in MEALS_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
    for stmt in PHOTO_ANALYSES_MEAL_RLS_STATEMENTS:
        await conn.execute(sa.text(stmt))
