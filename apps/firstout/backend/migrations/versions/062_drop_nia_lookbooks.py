"""Drop Nia, lookbooks, and storefront exception tables.

Revision ID: 062_drop_nia_lookbooks
Revises: 061_live_commerce_exceptions

Staff merchandising for the public shop is gone. Product groups and
skus.storefront_published stay: the ops-commerce product feed still groups
and filters on them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "062_drop_nia_lookbooks"
down_revision: Union[str, Sequence[str], None] = "061_live_commerce_exceptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RESTORE_ORDER = (
    "037_nia_threads",
    "038_nia_hitl",
    "039_nia_caps",
    "040_nia_audit",
    "041_nia_schedule",
    "051_lookbooks",
    "052_lookbook_events",
    "060_storefront_exceptions",
    "061_live_commerce_exceptions",
)


def upgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE key IN ('nia.use', 'nia.admin')")
    op.drop_column("users", "nia_monthly_token_cap")
    op.drop_column("team_settings", "nia_monthly_token_cap")
    for table in (
        "nia_scheduled_runs",
        "nia_scheduled_tasks",
        "nia_audit_events",
        "nia_usage_events",
        "nia_messages",
        "nia_threads",
        "lookbook_quotes",
        "lookbook_events",
        "lookbook_items",
        "lookbooks",
        "storefront_exception_commands",
        "storefront_exception_projections",
        "storefront_exception_alerts",
        "storefront_exception_audits",
        "storefront_commerce_exceptions",
    ):
        op.drop_table(table)


def _load_revision(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def downgrade() -> None:
    for name in _RESTORE_ORDER:
        _load_revision(name).upgrade()
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, key) "
            "SELECT roles.id, keys.key FROM roles "
            "CROSS JOIN (VALUES ('nia.use'), ('nia.admin')) AS keys(key) "
            "WHERE roles.slug = 'owner' "
            "ON CONFLICT (role_id, key) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, key) "
            "SELECT roles.id, 'nia.use' FROM roles "
            "WHERE roles.slug IN ('buyer', 'warehouse', 'till', 'books') "
            "ON CONFLICT (role_id, key) DO NOTHING"
        )
    )
