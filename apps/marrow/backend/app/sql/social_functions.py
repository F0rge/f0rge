from __future__ import annotations

CREATE_NOTIFICATION_SQL = """
CREATE OR REPLACE FUNCTION create_notification(recipient uuid, notif_type text, notif_payload jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE nid uuid;
BEGIN
    INSERT INTO notifications (user_id, type, payload)
    VALUES (recipient, notif_type, notif_payload)
    RETURNING id INTO nid;
    RETURN nid;
END;
$$;
"""

NOTIFICATIONS_RLS_SQL = """
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notifications_owner ON notifications;
CREATE POLICY notifications_owner ON notifications
    FOR ALL
    USING (user_id = current_setting('app.user_id', true)::uuid)
    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);
"""

SOCIAL_NOTIFIER_POLICY_SQL = """
CREATE POLICY social_notifier ON notifications
    FOR INSERT
    WITH CHECK (current_setting('app.service_role', true) = 'social_notifier')
"""

SOCIAL_LOOKUP_GROUPS_POLICY_SQL = """
CREATE POLICY social_lookup ON groups
    FOR SELECT
    USING (current_setting('app.service_role', true) = 'social_lookup')
"""

SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL = """
CREATE POLICY social_lookup ON group_members
    FOR SELECT
    USING (current_setting('app.service_role', true) = 'social_lookup')
"""

IS_GROUP_MEMBER_SQL = """
CREATE OR REPLACE FUNCTION is_group_member(gid uuid, uid uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE result boolean;
BEGIN
    PERFORM set_config('app.service_role', 'social_lookup', true);
    SELECT EXISTS (
        SELECT 1 FROM group_members WHERE group_id = gid AND user_id = uid
    ) INTO result;
    PERFORM set_config('app.service_role', '', true);
    RETURN result;
END;
$$;
"""

IS_GROUP_OWNER_SQL = """
CREATE OR REPLACE FUNCTION is_group_owner(gid uuid, uid uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE result boolean;
BEGIN
    PERFORM set_config('app.service_role', 'social_lookup', true);
    SELECT EXISTS (
        SELECT 1 FROM groups WHERE id = gid AND owner_id = uid
    ) INTO result;
    PERFORM set_config('app.service_role', '', true);
    RETURN result;
END;
$$;
"""
