"""Automatic invoice payment reminders.

Revision ID: 067_payment_reminders
Revises: 066_partial_payments

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "067_payment_reminders"
down_revision: Union[str, Sequence[str], None] = "066_partial_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "payment_reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "team_settings",
        sa.Column("payment_reminder_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("payment_reminders_last_run_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "payment_reminders_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tax_invoices",
        sa.Column(
            "reminders_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "payment_reminder_sends",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offset_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("comms_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount_owing", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["comms_message_id"], ["comms_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["tax_invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "invoice_id",
            "offset_days",
            name="uq_payment_reminder_sends_invoice_offset",
        ),
    )
    op.create_index(
        "ix_payment_reminder_sends_invoice_id",
        "payment_reminder_sends",
        ["invoice_id"],
    )
    op.drop_constraint("ck_comms_messages_document_type", "comms_messages", type_="check")
    op.create_check_constraint(
        "ck_comms_messages_document_type",
        "comms_messages",
        "document_type IN ('invoice', 'credit_note', 'layby', 'payment_reminder')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_comms_messages_document_type", "comms_messages", type_="check")
    op.create_check_constraint(
        "ck_comms_messages_document_type",
        "comms_messages",
        "document_type IN ('invoice', 'credit_note', 'layby')",
    )
    op.drop_index("ix_payment_reminder_sends_invoice_id", table_name="payment_reminder_sends")
    op.drop_table("payment_reminder_sends")
    op.drop_column("tax_invoices", "reminders_paused")
    op.drop_column("customers", "payment_reminders_opt_out")
    op.drop_column("team_settings", "payment_reminders_last_run_on")
    op.drop_column("team_settings", "payment_reminder_steps")
    op.drop_column("team_settings", "payment_reminders_enabled")
