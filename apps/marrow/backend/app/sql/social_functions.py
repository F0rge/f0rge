from __future__ import annotations

CREATE_NOTIFICATION_SQL = """
CREATE OR REPLACE FUNCTION create_notification(recipient uuid, notif_type text, notif_payload jsonb)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET row_security = off
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

IS_GROUP_MEMBER_SQL = """
CREATE OR REPLACE FUNCTION is_group_member(gid uuid, uid uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET row_security = off
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM group_members WHERE group_id = gid AND user_id = uid
    );
$$;
"""

IS_GROUP_OWNER_SQL = """
CREATE OR REPLACE FUNCTION is_group_owner(gid uuid, uid uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET row_security = off
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM groups WHERE id = gid AND owner_id = uid
    );
$$;
"""
