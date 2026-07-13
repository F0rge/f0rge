"""groups

Revision ID: 037
Revises: 036
Create Date: 2026-07-12 00:00:00.000000

Groups + group_members with recursion-breaking SECURITY DEFINER helpers (#306).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.sql.social_functions import (
    IS_GROUP_MEMBER_SQL,
    IS_GROUP_OWNER_SQL,
    SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL,
    SOCIAL_LOOKUP_GROUPS_POLICY_SQL,
)

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_GROUPS_RLS = [
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
]

_GROUP_MEMBERS_RLS = [
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
]


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_groups_name_len"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_groups_owner_id", "groups", ["owner_id"])

    op.create_table(
        "group_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), server_default="member", nullable=False),
        sa.Column("status", sa.Text(), server_default="invited", nullable=False),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now() at time zone 'utc')"),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_group_members_role"),
        sa.CheckConstraint("status IN ('invited', 'joined')", name="ck_group_members_status"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_pair"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])

    bind = op.get_bind()
    bind.execute(sa.text(SOCIAL_LOOKUP_GROUPS_POLICY_SQL))
    bind.execute(sa.text(SOCIAL_LOOKUP_GROUP_MEMBERS_POLICY_SQL))
    bind.execute(sa.text(IS_GROUP_MEMBER_SQL))
    bind.execute(sa.text(IS_GROUP_OWNER_SQL))
    for stmt in _GROUPS_RLS:
        bind.execute(sa.text(stmt))
    for stmt in _GROUP_MEMBERS_RLS:
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    for policy in (
        "group_members_delete",
        "group_members_update",
        "group_members_insert",
        "group_members_select",
    ):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON group_members"))
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON group_members"))
    bind.execute(sa.text("ALTER TABLE group_members NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE group_members DISABLE ROW LEVEL SECURITY"))

    for policy in ("groups_delete", "groups_update", "groups_insert", "groups_select"):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON groups"))
    bind.execute(sa.text("DROP POLICY IF EXISTS social_lookup ON groups"))
    bind.execute(sa.text("ALTER TABLE groups NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE groups DISABLE ROW LEVEL SECURITY"))

    bind.execute(sa.text("DROP FUNCTION IF EXISTS is_group_owner(uuid, uuid)"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS is_group_member(uuid, uuid)"))

    op.drop_index("ix_group_members_user_id", table_name="group_members")
    op.drop_table("group_members")
    op.drop_index("ix_groups_owner_id", table_name="groups")
    op.drop_table("groups")
