"""Nia HITL deferred-tool persistence on threads.

Revision ID: 038_nia_hitl
Revises: 037_nia_threads
Create Date: 2026-09-02

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038_nia_hitl"
down_revision: Union[str, Sequence[str], None] = "037_nia_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "nia_threads",
        sa.Column(
            "pending_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "nia_threads",
        sa.Column(
            "agent_messages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("nia_threads", "agent_messages")
    op.drop_column("nia_threads", "pending_tools")
