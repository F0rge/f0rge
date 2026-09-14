"""WhatsApp Cloud API columns on team_settings.

Revision ID: 049_comms_whatsapp
Revises: 048_comms_smtp
Create Date: 2026-09-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049_comms_whatsapp"
down_revision: Union[str, Sequence[str], None] = "048_comms_smtp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column("wa_phone_number_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("wa_business_account_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("wa_access_token_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("wa_app_secret_encrypted", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column("wa_invoice_template_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "team_settings",
        sa.Column(
            "wa_template_lang",
            sa.String(length=16),
            nullable=False,
            server_default="en",
        ),
    )


def downgrade() -> None:
    op.drop_column("team_settings", "wa_template_lang")
    op.drop_column("team_settings", "wa_invoice_template_name")
    op.drop_column("team_settings", "wa_app_secret_encrypted")
    op.drop_column("team_settings", "wa_access_token_encrypted")
    op.drop_column("team_settings", "wa_business_account_id")
    op.drop_column("team_settings", "wa_phone_number_id")
