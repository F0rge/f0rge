"""social_notifier FOR ALL policy

Revision ID: 040
Revises: 039
Create Date: 2026-07-12 00:00:00.000000

Match provisioner_copy pattern: social_notifier must be FOR ALL so INSERT
WITH CHECK passes under FORCE RLS on Fly MPG (schema_admin / NOBYPASSRLS).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.social_functions import CREATE_NOTIFICATION_SQL, SOCIAL_NOTIFIER_POLICY_SQL

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS social_notifier ON notifications"))
    bind.execute(sa.text(SOCIAL_NOTIFIER_POLICY_SQL))
    bind.execute(sa.text(CREATE_NOTIFICATION_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS social_notifier ON notifications"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY social_notifier ON notifications
                FOR INSERT
                WITH CHECK (current_setting('app.service_role', true) = 'social_notifier')
            """
        )
    )
