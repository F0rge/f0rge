"""Comms outbox for outbound email and WhatsApp.

Revision ID: 047_comms_outbox
Revises: 046_session_ttl_hours
Create Date: 2026-09-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047_comms_outbox"
down_revision: Union[str, Sequence[str], None] = "046_session_ttl_hours"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_address", sa.String(length=255), nullable=False),
        sa.Column("from_identity", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.CheckConstraint("channel IN ('email', 'whatsapp')", name="ck_comms_messages_channel"),
        sa.CheckConstraint(
            "provider IN ('smtp', 'whatsapp_click', 'whatsapp_cloud')",
            name="ck_comms_messages_provider",
        ),
        sa.CheckConstraint(
            "document_type IN ('invoice', 'credit_note', 'layby')",
            name="ck_comms_messages_document_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'opened')",
            name="ck_comms_messages_status",
        ),
    )
    op.create_index(
        "ix_comms_messages_document", "comms_messages", ["document_type", "document_id"]
    )
    op.create_index("ix_comms_messages_created_at", "comms_messages", ["created_at"])
    op.create_index("ix_comms_messages_actor_user_id", "comms_messages", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_comms_messages_actor_user_id", table_name="comms_messages")
    op.drop_index("ix_comms_messages_created_at", table_name="comms_messages")
    op.drop_index("ix_comms_messages_document", table_name="comms_messages")
    op.drop_table("comms_messages")
