"""byok_and_embeddings

Revision ID: c9f82b4d1e73
Revises: a1b2c3d4e5f6
Create Date: 2026-05-16 00:00:00.000000

Adds user_settings (BYOK singleton) and embedding (pgvector) tables.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "c9f82b4d1e73"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # Must install vector extension before any VECTOR column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "llm_provider", sa.String(), nullable=False, server_default="openrouter"
        ),
        sa.Column("llm_api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("llm_model", sa.String(), nullable=True),
        sa.Column(
            "embedding_provider",
            sa.String(),
            nullable=False,
            server_default="openrouter",
        ),
        sa.Column("embedding_api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("external_api_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("id = 1", name="user_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "embedding",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_table", sa.String(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_table",
            "source_id",
            "chunk_index",
            "embedding_model",
            name="uq_embedding_source_chunk_model",
        ),
    )

    op.create_index(
        "hnsw_embedding_cosine",
        "embedding",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("hnsw_embedding_cosine", table_name="embedding")
    op.drop_table("embedding")
    op.drop_table("user_settings")
    # Deliberately NOT dropping the vector extension — it may be used by other things.
