"""fly_app_role

Revision ID: e8f1a2b3c4d5
Revises: f7e6d5c4b3a2
Create Date: 2026-07-09 00:00:00.000000

Creates ``healthtracker_app`` — a non-superuser application role for the API
and worker. Used on Fly Managed Postgres so RLS policies (Phase 7) apply to
the backend connection; the MPG owner role bypasses RLS.

Set before running:

    export HEALTHTRACKER_APP_PASSWORD="<long-random-secret>"
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, None] = "018"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    if os.environ.get("FLY_MPG_SKIP_ROLE_DDL", "").lower() in ("1", "true", "yes"):
        return

    pw = os.environ.get("HEALTHTRACKER_APP_PASSWORD")
    if not pw:
        raise RuntimeError(
            "HEALTHTRACKER_APP_PASSWORD env var must be set before running this migration"
        )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_app'
                ) THEN
                    CREATE ROLE healthtracker_app
                        WITH LOGIN
                        NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
                END IF;
            END
            $$;
            """
        )
    )
    escaped_pw = pw.replace("'", "''")
    bind.execute(sa.text(f"ALTER ROLE healthtracker_app PASSWORD '{escaped_pw}'"))

    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'GRANT CONNECT ON DATABASE %I TO healthtracker_app',
                    current_database()
                );
            END
            $$;
            """
        )
    )
    bind.execute(sa.text("GRANT USAGE ON SCHEMA public TO healthtracker_app"))
    bind.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            "TO healthtracker_app"
        )
    )
    bind.execute(
        sa.text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO healthtracker_app")
    )
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO healthtracker_app"
        )
    )
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO healthtracker_app"
        )
    )


def downgrade() -> None:
    if os.environ.get("FLY_MPG_SKIP_ROLE_DDL", "").lower() in ("1", "true", "yes"):
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM healthtracker_app"
        )
    )
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            "REVOKE USAGE, SELECT ON SEQUENCES FROM healthtracker_app"
        )
    )
    bind.execute(
        sa.text("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM healthtracker_app")
    )
    bind.execute(
        sa.text("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM healthtracker_app")
    )
    bind.execute(sa.text("REVOKE USAGE ON SCHEMA public FROM healthtracker_app"))
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'REVOKE CONNECT ON DATABASE %I FROM healthtracker_app',
                    current_database()
                );
            END
            $$;
            """
        )
    )
    bind.execute(sa.text("DROP ROLE IF EXISTS healthtracker_app"))
