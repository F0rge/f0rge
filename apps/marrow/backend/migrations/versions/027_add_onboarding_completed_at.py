"""add_onboarding_completed_at

Revision ID: 027
Revises: 026
Create Date: 2026-07-10 00:00:00.000000

Adds onboarding_completed_at to user_settings. Backfills existing rows so
current users are not forced through the onboarding tour.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
    )
    bind = op.get_bind()
    # Fly MPG runs alembic as schema_admin with FORCE RLS enabled — without
    # app.user_id set, tenant policies hide all rows and break cross-user backfill.
    bind.execute(sa.text("ALTER TABLE user_settings DISABLE ROW LEVEL SECURITY"))
    bind.execute(
        sa.text(
            "UPDATE user_settings SET onboarding_completed_at = NOW() "
            "WHERE onboarding_completed_at IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO user_settings "
            "(user_id, llm_provider, embedding_provider, onboarding_completed_at, created_at, updated_at) "
            "SELECT u.id, 'openrouter', 'openrouter', NOW(), NOW(), NOW() "
            "FROM users u "
            "WHERE NOT EXISTS (SELECT 1 FROM user_settings us WHERE us.user_id = u.id)"
        )
    )
    bind.execute(sa.text("ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE user_settings FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.drop_column("user_settings", "onboarding_completed_at")
