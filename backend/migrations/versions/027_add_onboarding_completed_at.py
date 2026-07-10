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

# Cross-tenant backfill must bypass RLS (migration 021). Same pattern as 022.
_BACKFILL_ONBOARDING_SQL = """
CREATE OR REPLACE FUNCTION backfill_onboarding_completed_at()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE user_settings
    SET onboarding_completed_at = NOW()
    WHERE onboarding_completed_at IS NULL;

    INSERT INTO user_settings (
        user_id,
        llm_provider,
        embedding_provider,
        onboarding_completed_at,
        created_at,
        updated_at
    )
    SELECT u.id, 'openrouter', 'openrouter', NOW(), NOW(), NOW()
    FROM users u
    WHERE NOT EXISTS (SELECT 1 FROM user_settings us WHERE us.user_id = u.id);
END;
$$;

SELECT backfill_onboarding_completed_at();

DROP FUNCTION backfill_onboarding_completed_at();
"""


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
    )
    op.execute(sa.text(_BACKFILL_ONBOARDING_SQL))


def downgrade() -> None:
    op.drop_column("user_settings", "onboarding_completed_at")
