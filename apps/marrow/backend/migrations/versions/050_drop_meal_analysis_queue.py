"""drop_meal_analysis_queue

Revision ID: 050
Revises: 049
Create Date: 2026-07-26 00:00:00.000000

Meal analysis is orchestrated by Airflow; the Postgres outbox is removed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS worker_queue ON meal_analysis_queue"))
    bind.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation ON meal_analysis_queue"))
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue NO FORCE ROW LEVEL SECURITY"))
    bind.execute(sa.text("ALTER TABLE meal_analysis_queue DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_meal_analysis_queue_enqueued", table_name="meal_analysis_queue")
    op.drop_index("ix_meal_analysis_queue_user_id", table_name="meal_analysis_queue")
    op.drop_table("meal_analysis_queue")


def downgrade() -> None:
    raise NotImplementedError("meal_analysis_queue was replaced by Airflow; restore from 049 if needed")
