"""Teams can design the layout their customer documents print with.

Additive only (P-020): a nullable column that code from before this release ignores.
Null means the default template.

Revision ID: 109_document_template
Revises: 108_invoice_archive
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "109_document_template"
down_revision = "108_invoice_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("team_settings", sa.Column("document_template", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("team_settings", "document_template")
