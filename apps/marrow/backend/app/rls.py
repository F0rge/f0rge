from __future__ import annotations

import sqlalchemy as sa
from f0rge_db.rls import create_service_role_policy, enable_tenant_isolation
from app.sql.social_functions import (
    CREATE_NOTIFICATION_SQL,
    IS_GROUP_MEMBER_SQL,
    IS_GROUP_OWNER_SQL,
)
from sqlalchemy.ext.asyncio import AsyncConnection

# Frozen import surface: migrations/versions/021_row_level_security.py does
# `from app.rls import USER_OWNED_TABLES` — this name must stay here forever.
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
    "user_settings",
    "diet_tag_catalog",
    "supplement_catalog",
    "symptom_catalog",
    "medication_catalog",
    "lab_marker_catalog",
    "lab_marker_aliases",
    "dietary_ingredients",
    "ingredient_aliases",
)

# The four catalog tables the signup copy touches (mirrors migration 032).
PROVISIONER_COPY_TABLES: tuple[str, ...] = (
    "dietary_ingredients",
    "ingredient_aliases",
    "lab_marker_catalog",
    "lab_marker_aliases",
)


async def enable_row_level_security(conn: AsyncConnection) -> None:
    """Apply tenant RLS policies (mirrors migrations 021 + 032)."""
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
        tables=("embedding_queue",),
        role="worker",
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
    statements = [
        "ALTER TABLE notifications ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE notifications FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS notifications_owner ON notifications",
        """
        CREATE POLICY notifications_owner ON notifications
            FOR ALL
            USING (user_id = current_setting('app.user_id', true)::uuid)
            WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """,
    ]
    for stmt in statements:
        await conn.execute(sa.text(stmt))
    await conn.execute(sa.text(CREATE_NOTIFICATION_SQL))

    connection_policies = [
        "ALTER TABLE connections ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE connections FORCE ROW LEVEL SECURITY",
        """
        CREATE POLICY connections_select ON connections FOR SELECT
            USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
        """,
        """
        CREATE POLICY connections_insert ON connections FOR INSERT
            WITH CHECK (
                requester_id = current_setting('app.user_id', true)::uuid
                AND current_setting('app.user_id', true)::uuid IN (user_low, user_high)
            )
        """,
        """
        CREATE POLICY connections_update ON connections FOR UPDATE
            USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
            WITH CHECK (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
        """,
        """
        CREATE POLICY connections_delete ON connections FOR DELETE
            USING (current_setting('app.user_id', true)::uuid IN (user_low, user_high))
        """,
    ]
    for stmt in connection_policies:
        await conn.execute(sa.text(stmt))

    await conn.execute(sa.text(IS_GROUP_MEMBER_SQL))
    await conn.execute(sa.text(IS_GROUP_OWNER_SQL))

    group_policies = [
        "ALTER TABLE groups ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE groups FORCE ROW LEVEL SECURITY",
        """
        CREATE POLICY groups_select ON groups FOR SELECT
            USING (
                owner_id = current_setting('app.user_id', true)::uuid
                OR is_group_member(id, current_setting('app.user_id', true)::uuid)
            )
        """,
        """
        CREATE POLICY groups_insert ON groups FOR INSERT
            WITH CHECK (owner_id = current_setting('app.user_id', true)::uuid)
        """,
        """
        CREATE POLICY groups_update ON groups FOR UPDATE
            USING (owner_id = current_setting('app.user_id', true)::uuid)
            WITH CHECK (owner_id = current_setting('app.user_id', true)::uuid)
        """,
        """
        CREATE POLICY groups_delete ON groups FOR DELETE
            USING (owner_id = current_setting('app.user_id', true)::uuid)
        """,
        "ALTER TABLE group_members ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE group_members FORCE ROW LEVEL SECURITY",
        # ponytail: invitees can read the member roster pre-join — acceptable at family scale.
        """
        CREATE POLICY group_members_select ON group_members FOR SELECT
            USING (
                user_id = current_setting('app.user_id', true)::uuid
                OR is_group_member(group_id, current_setting('app.user_id', true)::uuid)
            )
        """,
        """
        CREATE POLICY group_members_insert ON group_members FOR INSERT
            WITH CHECK (
                user_id = current_setting('app.user_id', true)::uuid
                OR is_group_member(group_id, current_setting('app.user_id', true)::uuid)
            )
        """,
        """
        CREATE POLICY group_members_update ON group_members FOR UPDATE
            USING (user_id = current_setting('app.user_id', true)::uuid)
            WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """,
        """
        CREATE POLICY group_members_delete ON group_members FOR DELETE
            USING (
                user_id = current_setting('app.user_id', true)::uuid
                OR is_group_owner(group_id, current_setting('app.user_id', true)::uuid)
            )
        """,
    ]
    for stmt in group_policies:
        await conn.execute(sa.text(stmt))
