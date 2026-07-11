"""consolidate_byok_key

Revision ID: 008
Revises: 007
Create Date: 2026-07-03 00:00:00.000000

Consolidates the two BYOK columns on user_settings into one.  Previously
llm_api_key_encrypted and embedding_api_key_encrypted were separate columns
resolved independently in app/services/llm/factory.py, even though both
always fell back to the same OPENROUTER_API_KEY env var. After this
migration there is a single stored key (llm_api_key_encrypted) used by both
the LLM client and the embedding client — models/providers remain separate,
only the credential consolidates.

Data-preserving: if a row only ever had an embedding key set (llm key was
never configured), that key is coalesced into llm_api_key_encrypted before
the column is dropped. Both columns are Fernet-encrypted with the same
SETTINGS_ENCRYPTION_KEY, so the ciphertext bytes are portable verbatim
between columns — no decrypt/re-encrypt needed.

Downgrade re-adds embedding_api_key_encrypted as a nullable column, but the
value is NOT recoverable — the coalesce direction is one-way and the
original two-key split can't be reconstructed from a single column.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE user_settings "
        "SET llm_api_key_encrypted = embedding_api_key_encrypted "
        "WHERE llm_api_key_encrypted IS NULL "
        "AND embedding_api_key_encrypted IS NOT NULL"
    )
    op.drop_column("user_settings", "embedding_api_key_encrypted")


def downgrade() -> None:
    """Downgrade schema. The embedding key value is not recoverable — the
    column is re-added nullable and empty."""
    op.add_column(
        "user_settings",
        sa.Column("embedding_api_key_encrypted", sa.LargeBinary(), nullable=True),
    )
