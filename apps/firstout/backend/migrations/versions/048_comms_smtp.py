"""SMTP mailbox columns on team_settings.

Revision ID: 048_comms_smtp
Revises: 047_comms_outbox
Create Date: 2026-09-14

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048_comms_smtp"
down_revision: Union[str, Sequence[str], None] = "047_comms_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_settings", sa.Column("smtp_host", sa.String(length=255), nullable=True))
    op.add_column("team_settings", sa.Column("smtp_port", sa.Integer(), nullable=True))
    op.add_column(
        "team_settings",
        sa.Column("smtp_security", sa.String(length=16), nullable=False, server_default="starttls"),
    )
    op.add_column("team_settings", sa.Column("smtp_username", sa.String(length=255), nullable=True))
    op.add_column(
        "team_settings", sa.Column("smtp_password_encrypted", sa.LargeBinary(), nullable=True)
    )
    op.add_column(
        "team_settings",
        sa.Column("smtp_from_address", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "team_settings", sa.Column("smtp_from_name", sa.String(length=255), nullable=True)
    )
    op.add_column("team_settings", sa.Column("smtp_reply_to", sa.String(length=255), nullable=True))
    op.create_check_constraint(
        "ck_team_settings_smtp_port",
        "team_settings",
        "smtp_port IS NULL OR (smtp_port >= 1 AND smtp_port <= 65535)",
    )
    op.create_check_constraint(
        "ck_team_settings_smtp_security",
        "team_settings",
        "smtp_security IN ('starttls', 'ssl', 'plain')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_team_settings_smtp_security", "team_settings", type_="check")
    op.drop_constraint("ck_team_settings_smtp_port", "team_settings", type_="check")
    op.drop_column("team_settings", "smtp_reply_to")
    op.drop_column("team_settings", "smtp_from_name")
    op.drop_column("team_settings", "smtp_from_address")
    op.drop_column("team_settings", "smtp_password_encrypted")
    op.drop_column("team_settings", "smtp_username")
    op.drop_column("team_settings", "smtp_security")
    op.drop_column("team_settings", "smtp_port")
    op.drop_column("team_settings", "smtp_host")
