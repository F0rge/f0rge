"""copy_user_catalog_from_reference

Revision ID: 022
Revises: 021
Create Date: 2026-07-09 23:00:00.000000

SECURITY DEFINER helper for signup-time catalog copy. Copies dietary
ingredients, ingredient aliases, lab marker catalog, and lab marker aliases
from the reference user (Leo) into a newly registered user. Required because
RLS (migration 021) blocks cross-tenant reads during in-process provisioning.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(COPY_USER_CATALOG_FROM_REFERENCE_SQL))
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_app') THEN
                    GRANT EXECUTE ON FUNCTION copy_user_catalog_from_reference(uuid, uuid)
                        TO healthtracker_app;
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_app') THEN
                    REVOKE EXECUTE ON FUNCTION copy_user_catalog_from_reference(uuid, uuid)
                        FROM healthtracker_app;
                END IF;
            END
            $$;
            """
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS copy_user_catalog_from_reference(uuid, uuid)"))
