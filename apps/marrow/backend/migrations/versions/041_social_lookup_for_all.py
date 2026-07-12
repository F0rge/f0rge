"""social_lookup FOR ALL policies

Revision ID: 041
Revises: 040
Create Date: 2026-07-12 00:00:00.000000

Match provisioner_copy / social_notifier: social_lookup must be FOR ALL so
is_group_member / is_group_owner SECURITY DEFINER helpers can read under
FORCE RLS on Fly MPG.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.social_functions import (
    IS_GROUP_MEMBER_SQL,
    IS_GROUP_OWNER_SQL,
    SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL,
    SOCIAL_LOOKUP_GROUPS_POLICY_SQL,
)

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON groups"))
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON group_members"))
    bind.execute(sa.text(SOCIAL_LOOKUP_GROUPS_POLICY_SQL))
    bind.execute(sa.text(SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL))
    bind.execute(sa.text(IS_GROUP_MEMBER_SQL))
    bind.execute(sa.text(IS_GROUP_OWNER_SQL))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON groups"))
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON group_members"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY social_lookup ON groups
                FOR SELECT
                USING (current_setting('app.service_role', true) = 'social_lookup')
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE POLICY social_lookup ON group_members
                FOR SELECT
                USING (current_setting('app.service_role', true) = 'social_lookup')
            """
        )
    )
