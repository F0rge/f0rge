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
