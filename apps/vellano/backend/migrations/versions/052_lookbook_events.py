"""Lookbook first-party events and quote links.

Revision ID: 052_lookbook_events
Revises: 051_lookbooks
Create Date: 2026-09-16

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "052_lookbook_events"
down_revision: Union[str, Sequence[str], None] = "051_lookbooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lookbook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("lookbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("visitor_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('open', 'sku_visible', 'sku_open', 'heart', 'unheart', 'submit')",
            name="ck_lookbook_events_type",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_lookbook_events_duration",
        ),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lookbook_events_lookbook_id", "lookbook_events", ["lookbook_id"])

    op.create_table(
        "lookbook_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("lookbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id", name="uq_lookbook_quotes_quote_id"),
    )
    op.create_index("ix_lookbook_quotes_lookbook_id", "lookbook_quotes", ["lookbook_id"])


def downgrade() -> None:
    op.drop_index("ix_lookbook_quotes_lookbook_id", table_name="lookbook_quotes")
    op.drop_table("lookbook_quotes")
    op.drop_index("ix_lookbook_events_lookbook_id", table_name="lookbook_events")
    op.drop_table("lookbook_events")
