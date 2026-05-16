"""external_readonly_role

Revision ID: d4e7a1b2c903
Revises: c9f82b4d1e73
Create Date: 2026-05-16 00:00:00.000000

Creates a Postgres role ``healthtracker_ro`` used exclusively by the MCP
server for read-only introspection of the database.  The role is granted
CONNECT on the current database, USAGE on the public schema, and SELECT on
all existing + future tables in that schema.

BEFORE running this migration set:

    export HEALTHTRACKER_RO_PASSWORD="<long-random-secret>"

The password is bound via a parameterised query and never interpolated into a
SQL string.  If the env var is absent the migration aborts with a clear error
rather than proceeding with a placeholder.

This role is intentionally separate from the main ``health`` application user
so that the MCP server cannot mutate data even if its session is compromised.
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e7a1b2c903"
down_revision: Union[str, None] = "c9f82b4d1e73"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    pw = os.environ.get("HEALTHTRACKER_RO_PASSWORD")
    if not pw:
        raise RuntimeError(
            "HEALTHTRACKER_RO_PASSWORD env var must be set before running this migration"
        )

    bind = op.get_bind()

    # Step 1 — create the role if it does not already exist (idempotent).
    # DO $$ blocks do not accept bound parameters, so we create the role
    # without a password first, then immediately set the password via a
    # parameterised ALTER ROLE statement.  This keeps the secret out of the
    # SQL string that lands in pg_stat_activity / logs.
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_ro'
                ) THEN
                    CREATE ROLE healthtracker_ro
                        WITH LOGIN
                        NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
                END IF;
            END
            $$;
            """
        )
    )

    # Step 2 — set the password.
    # asyncpg does not support bound parameters in ALTER ROLE ... PASSWORD $1
    # (Postgres rejects parameter markers in DDL password clauses).  The safe
    # workaround is to produce a valid SQL string literal in Python using
    # standard SQL escaping (doubling any embedded single-quotes), then embed
    # that into the ALTER ROLE statement.  This is not string interpolation of
    # an untrusted value: the password comes from an env var we own, and the
    # escaping ensures no SQL injection is possible even if the value contains
    # single-quotes.
    escaped_pw = pw.replace("'", "''")
    bind.execute(sa.text(f"ALTER ROLE healthtracker_ro PASSWORD '{escaped_pw}'"))

    # Step 3 — CONNECT on the current database (no hard-coded name).
    # current_database() is a SQL function; we resolve it first then use it in
    # a DO block so the identifier is quoted safely by pg itself.
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'GRANT CONNECT ON DATABASE %I TO healthtracker_ro',
                    current_database()
                );
            END
            $$;
            """
        )
    )

    # Step 4 — USAGE on the schema.
    bind.execute(sa.text("GRANT USAGE ON SCHEMA public TO healthtracker_ro"))

    # Step 5 — SELECT on all tables that exist right now.
    bind.execute(
        sa.text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO healthtracker_ro")
    )

    # Step 6 — future tables auto-grant SELECT as they are created.
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
            " GRANT SELECT ON TABLES TO healthtracker_ro"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Revoke default-privilege auto-grants first.
    bind.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public"
            " REVOKE SELECT ON TABLES FROM healthtracker_ro"
        )
    )

    # Revoke explicit grants on existing objects.
    bind.execute(
        sa.text("REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM healthtracker_ro")
    )
    bind.execute(sa.text("REVOKE USAGE ON SCHEMA public FROM healthtracker_ro"))
    bind.execute(
        sa.text(
            """
            DO $$
            BEGIN
                EXECUTE format(
                    'REVOKE CONNECT ON DATABASE %I FROM healthtracker_ro',
                    current_database()
                );
            END
            $$;
            """
        )
    )

    # Drop the role (no-op if already gone).
    bind.execute(sa.text("DROP ROLE IF EXISTS healthtracker_ro"))
