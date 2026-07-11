"""move_joint_neuro_to_symptoms

Revision ID: 031
Revises: 030
Create Date: 2026-07-11 14:00:00.000000

Retire core entry columns joint_pain / neuro as user-facing scales. Relabel the
existing bulk symptom joint_pain, add neuro_symptoms to every user's catalog
(archived except Leo), and backfill symptoms_json from legacy column values.
"""

from __future__ import annotations

import datetime
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

# Frozen at migration time — same keys/labels as app/seed_data.py BULK_SYMPTOMS.
_CATALOG_ROWS: tuple[tuple[str, str], ...] = (
    ("joint_pain", "Joint pain / crepitus"),
    ("neuro_symptoms", "Neuro symptoms"),
)


def _leo_email() -> str:
    return os.environ.get("LEO_USER_EMAIL", "leo.defig@gmail.com")


def _fallback_leo_user_id() -> str:
    return os.environ.get("DEFAULT_STORAGE_USER_ID", "00000000-0000-0000-0000-000000000001")


def _resolve_leo_user_id(bind: sa.Connection) -> str:
    row = bind.execute(
        sa.text("SELECT id::text FROM users WHERE email = :email LIMIT 1"),
        {"email": _leo_email()},
    ).fetchone()
    if row is not None:
        return row[0]
    return _fallback_leo_user_id()


def upgrade() -> None:
    bind = op.get_bind()
    leo_user_id = _resolve_leo_user_id(bind)
    now = datetime.datetime.utcnow()

    bind.execute(
        sa.text(
            """
            UPDATE symptom_catalog
            SET label = 'Joint pain / crepitus', updated_at = :now
            WHERE key = 'joint_pain'
            """
        ),
        {"now": now},
    )

    for key, label in _CATALOG_ROWS:
        bind.execute(
            sa.text(
                """
                INSERT INTO symptom_catalog (
                    user_id, key, label, archived, sort_order, created_at, updated_at
                )
                SELECT
                    u.id,
                    :key,
                    :label,
                    CASE WHEN u.id::text = :leo_id THEN false ELSE true END,
                    COALESCE(
                        (SELECT MAX(sc.sort_order) FROM symptom_catalog sc WHERE sc.user_id = u.id),
                        -1
                    ) + 1,
                    :now,
                    :now
                FROM users u
                ON CONFLICT ON CONSTRAINT uq_symptom_catalog_user_id_key DO NOTHING
                """
            ),
            {"key": key, "label": label, "leo_id": leo_user_id, "now": now},
        )

    bind.execute(
        sa.text(
            """
            UPDATE symptom_catalog
            SET archived = false, updated_at = :now
            WHERE user_id::text = :leo_id
              AND key = ANY(:keys)
            """
        ),
        {
            "leo_id": leo_user_id,
            "keys": [key for key, _ in _CATALOG_ROWS],
            "now": now,
        },
    )

    bind.execute(
        sa.text(
            """
            UPDATE entries
            SET symptoms_json = symptoms_json || jsonb_build_object(
                'joint_pain',
                CASE joint_pain
                    WHEN 1 THEN 3
                    WHEN 2 THEN 7
                    WHEN 3 THEN 10
                END
            )
            WHERE joint_pain > 0
              AND NOT COALESCE(symptoms_json, '{}'::jsonb) ? 'joint_pain'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE entries
            SET symptoms_json = symptoms_json || jsonb_build_object(
                'neuro_symptoms',
                LEAST(10, ROUND(((5 - neuro) * 10.0) / 4))
            )
            WHERE schema_version >= 4
              AND neuro BETWEEN 1 AND 5
              AND NOT COALESCE(symptoms_json, '{}'::jsonb) ? 'neuro_symptoms'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE entries
            SET symptoms_json = symptoms_json || jsonb_build_object(
                'neuro_symptoms',
                CASE neuro
                    WHEN -1 THEN 8
                    WHEN 1 THEN 2
                END
            )
            WHERE schema_version < 4
              AND neuro IN (-1, 1)
              AND NOT COALESCE(symptoms_json, '{}'::jsonb) ? 'neuro_symptoms'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE entries
            SET symptoms_json = symptoms_json - 'joint_pain' - 'neuro_symptoms'
            WHERE symptoms_json ?| ARRAY['joint_pain', 'neuro_symptoms']
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM symptom_catalog
            WHERE key = 'neuro_symptoms'
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE symptom_catalog
            SET label = 'Joint Pain'
            WHERE key = 'joint_pain'
            """
        )
    )
