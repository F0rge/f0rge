"""meal_analysis_queue

Revision ID: 049
Revises: 048
Create Date: 2026-07-26 00:00:00.000000

Durable outbox for staged meal photo analysis (extract → enrich → gate → persist).
Mirrors embedding_queue: SKIP LOCKED worker, LISTEN/NOTIFY wake, tenant RLS +
worker service-role policy.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from f0rge_db.rls import create_service_role_policy_sync

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_analysis_queue",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meal_id",
            sa.Integer(),
            sa.ForeignKey("meals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            sa.Integer(),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.UniqueConstraint("meal_id", name="uq_meal_analysis_queue_meal_id"),
    )
    op.create_index("ix_meal_analysis_queue_user_id", "meal_analysis_queue", ["user_id"])
    op.create_index(
        "ix_meal_analysis_queue_enqueued",
        "meal_analysis_queue",
        ["enqueued_at"],
        postgresql_where=sa.text("attempts < 5"),
    )

    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue ENABLE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue FORCE ROW LEVEL SECURITY"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY tenant_isolation ON meal_analysis_queue
                FOR ALL
                USING (user_id = current_setting('app.user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
            """
        )
    )
    create_service_role_policy_sync(
        bind,
        name="worker_queue",
        tables=("meal_analysis_queue",),
        role="worker",
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS worker_queue ON meal_analysis_queue"))
    bind.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON meal_analysis_queue"))
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_meal_analysis_queue_enqueued", table_name="meal_analysis_queue")
    op.drop_index("ix_meal_analysis_queue_user_id", table_name="meal_analysis_queue")
    op.drop_table("meal_analysis_queue")
