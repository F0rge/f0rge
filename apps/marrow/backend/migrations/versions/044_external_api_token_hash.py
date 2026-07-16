"""external_api_token_hash

Revision ID: 044
Revises: 043
Create Date: 2026-07-16 00:00:00.000000

Add sha256 hash column for O(1) MCP Bearer token lookup. Backfill from
encrypted tokens where SETTINGS_ENCRYPTION_KEY can decrypt them.
"""

from __future__ import annotations

import hashlib
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken

from f0rge_db.rls import migration_bypass

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _fernet_from_env() -> Fernet | None:
    key = os.environ.get("SETTINGS_ENCRYPTION_KEY", "")
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def _backfill_token_hashes(bind: sa.Connection) -> None:
    fernet = _fernet_from_env()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, external_api_token_encrypted
            FROM user_settings
            WHERE external_api_token_encrypted IS NOT NULL
            """
        )
    ).fetchall()

    for row_id, ciphertext in rows:
        token_hash: str | None = None
        if fernet is not None and ciphertext is not None:
            try:
                plaintext = fernet.decrypt(ciphertext).decode()
                token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
            except (InvalidToken, ValueError, TypeError):
                token_hash = None
        bind.execute(
            sa.text(
                "UPDATE user_settings SET external_api_token_hash = :token_hash WHERE id = :row_id"
            ),
            {"token_hash": token_hash, "row_id": row_id},
        )


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("external_api_token_hash", sa.String(length=64), nullable=True),
    )

    bind = op.get_bind()
    with migration_bypass(bind, ("user_settings",)):
        _backfill_token_hashes(bind)

    op.create_index(
        "uq_user_settings_external_api_token_hash",
        "user_settings",
        ["external_api_token_hash"],
        unique=True,
        postgresql_where=sa.text("external_api_token_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_user_settings_external_api_token_hash",
        table_name="user_settings",
        postgresql_where=sa.text("external_api_token_hash IS NOT NULL"),
    )
    op.drop_column("user_settings", "external_api_token_hash")
