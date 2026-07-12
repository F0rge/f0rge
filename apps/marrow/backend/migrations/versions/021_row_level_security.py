"""row_level_security

Revision ID: 021
Revises: 020
Create Date: 2026-07-09 12:00:00.000000

Enable FORCE ROW LEVEL SECURITY on every user-owned table with tenant
isolation policies keyed on ``current_setting('app.user_id', true)::uuid``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# frozen copy of app.rls.py USER_OWNED_TABLES as of revision 021 — do NOT import
# the live list; new tables get RLS in their own migrations.
_USER_OWNED_TABLES_021: tuple[str, ...] = (
    "entries",
    "photos",
    "photo_analyses",
    "photo_ingredients",
    "tracker",
    "tracker_log",
    "treatments",
    "treatment_log",
    "labs",
    "lab_markers",
    "health_metrics",
    "weather_readings",
    "embedding",
    "embedding_queue",
    "user_settings",
    "diet_tag_catalog",
    "supplement_catalog",
    "symptom_catalog",
    "medication_catalog",
    "lab_marker_catalog",
    "lab_marker_aliases",
    "dietary_ingredients",
    "ingredient_aliases",
)

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in _USER_OWNED_TABLES_021:
        bind.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        bind.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                    FOR ALL
                    USING (user_id = current_setting('app.user_id', true)::uuid)
                    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
                """
            )
        )
    bind.execute(
        sa.text(
            """
            CREATE POLICY mcp_auth_lookup ON user_settings
                FOR SELECT
                USING (current_setting('app.service_role', true) = 'mcp_auth')
            """
        )
    )
    bind.execute(
        sa.text(
            """
            CREATE POLICY worker_queue ON embedding_queue
                FOR ALL
                USING (current_setting('app.service_role', true) = 'worker')
                WITH CHECK (current_setting('app.service_role', true) = 'worker')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP POLICY IF EXISTS worker_queue ON embedding_queue"))
    bind.execute(sa.text("DROP POLICY IF EXISTS mcp_auth_lookup ON user_settings"))
    for table in reversed(_USER_OWNED_TABLES_021):
        bind.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        bind.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
