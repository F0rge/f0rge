"""Append-only books document history.

Revision ID: 028_books_events
Revises: 027_repeating_invoices
Create Date: 2026-09-01

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "028_books_events"
down_revision: Union[str, Sequence[str], None] = "027_repeating_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "books_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_books_events_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_books_events"),
        sa.CheckConstraint(
            "document_type IN ('invoice', 'bill', 'payment', 'journal')",
            name="ck_books_events_document_type",
        ),
        sa.CheckConstraint(
            "action IN ('created', 'posted', 'voided')",
            name="ck_books_events_action",
        ),
    )
    op.create_index("ix_books_events_document_id", "books_events", ["document_id"])
    op.create_index("ix_books_events_actor_user_id", "books_events", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_books_events_actor_user_id", table_name="books_events")
    op.drop_index("ix_books_events_document_id", table_name="books_events")
    op.drop_table("books_events")
