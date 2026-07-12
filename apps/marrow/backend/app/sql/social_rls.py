"""Canonical social-layer RLS DDL — mirrored in Alembic migrations and ``app.rls``."""

from __future__ import annotations

NOTIFICATIONS_RLS_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE notifications ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE notifications FORCE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS notifications_owner ON notifications",
    """
    CREATE POLICY notifications_owner ON notifications
        FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
    """,
)

CONNECTIONS_RLS_STATEMENTS: tuple[str, ...] = (
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
)

GROUPS_RLS_STATEMENTS: tuple[str, ...] = (
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
)

GROUP_MEMBERS_RLS_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE group_members ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE group_members FORCE ROW LEVEL SECURITY",
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
)

MEAL_TAGS_RLS_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE meal_tags ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE meal_tags FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY meal_tags_select ON meal_tags FOR SELECT
        USING (current_setting('app.user_id', true)::uuid IN (tagger_id, tagged_user_id))
    """,
    """
    CREATE POLICY meal_tags_insert ON meal_tags FOR INSERT
        WITH CHECK (tagger_id = current_setting('app.user_id', true)::uuid)
    """,
    """
    CREATE POLICY meal_tags_update ON meal_tags FOR UPDATE
        USING (current_setting('app.user_id', true)::uuid IN (tagger_id, tagged_user_id))
        WITH CHECK (current_setting('app.user_id', true)::uuid IN (tagger_id, tagged_user_id))
    """,
    """
    CREATE POLICY meal_tags_delete ON meal_tags FOR DELETE
        USING (tagger_id = current_setting('app.user_id', true)::uuid)
    """,
)

SOCIAL_TABLES: tuple[str, ...] = (
    "notifications",
    "connections",
    "groups",
    "group_members",
    "meal_tags",
)
