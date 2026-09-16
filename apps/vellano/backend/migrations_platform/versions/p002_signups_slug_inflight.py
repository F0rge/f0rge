"""partial unique index on inflight signup slugs

Revision ID: p002_signups_slug_inflight
Revises: p001_platform_registry
Create Date: 2026-09-16

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "p002_signups_slug_inflight"
down_revision: Union[str, Sequence[str], None] = "p001_platform_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_signups_slug_inflight
        ON signups (slug)
        WHERE status IN ('pending_verify', 'verified', 'provisioning')
        """
    )


def downgrade() -> None:
    op.drop_index("uq_signups_slug_inflight", table_name="signups")
