"""fix create_notification RLS

Revision ID: 039
Revises: 038
Create Date: 2026-07-12 00:00:00.000000

Set app.service_role inside create_notification SECURITY DEFINER so cross-user
inserts pass social_notifier policy on managed Postgres (Fly MPG).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.social_functions import CREATE_NOTIFICATION_SQL, SOCIAL_NOTIFIER_POLICY_SQL

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS social_notifier ON notifications"))
    bind.execute(sa.text(SOCIAL_NOTIFIER_POLICY_SQL))
    bind.execute(sa.text(CREATE_NOTIFICATION_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
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
        )
    )
