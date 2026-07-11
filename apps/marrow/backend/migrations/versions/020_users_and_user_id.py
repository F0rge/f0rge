"""users_and_user_id

Revision ID: 020
Revises: e8f1a2b3c4d5
Create Date: 2026-07-09 00:00:00.000000

Creates ``users``, adds ``user_id`` to every user-owned table, fixes
single-user uniqueness constraints to be per-user, backfills all existing
rows to Leo's user, then enforces NOT NULL + FK ON DELETE CASCADE.

Set before running (optional overrides):

    export LEO_USER_EMAIL="leo@health-tracker.local"
    export DEFAULT_STORAGE_USER_ID="00000000-0000-0000-0000-000000000001"
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "e8f1a2b3c4d5"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

LEO_PLACEHOLDER_HASH = "$2b$12$placeholderplaceholderplaceholderplac"

USER_OWNED_TABLES: tuple[str, ...] = (
    "entries",
    "photos",
    "photo_analyses",
    "photo_ingredients",
    "tracker",
    "tracker_log",
    "treatments",
    "treatment_log",
    "labs",
    "lab_markers",
    "health_metrics",
    "weather_readings",
    "embedding",
    "embedding_queue",
    "user_settings",
    "diet_tag_catalog",
    "supplement_catalog",
    "symptom_catalog",
    "medication_catalog",
    "lab_marker_catalog",
    "lab_marker_aliases",
    "dietary_ingredients",
    "ingredient_aliases",
)


def _leo_user_id() -> str:
    return os.environ.get("DEFAULT_STORAGE_USER_ID", "00000000-0000-0000-0000-000000000001")


def _leo_email() -> str:
    return os.environ.get("LEO_USER_EMAIL", "leo@health-tracker.local")


def _add_nullable_user_id(table: str) -> None:
    op.add_column(
        table,
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
    )


def _backfill_user_id(table: str, leo_id: str) -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
        {"uid": leo_id},
    )


def _set_user_id_not_null(table: str) -> None:
    op.alter_column(table, "user_id", nullable=False)


def _add_user_fk(table: str) -> None:
    op.create_foreign_key(
        f"fk_{table}_user_id_users",
        table,
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _add_user_id_index(table: str) -> None:
    op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def upgrade() -> None:
    leo_id = _leo_user_id()
    leo_email = _leo_email()

    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO users (id, email, password_hash, created_at)
            VALUES (:id, :email, :password_hash, now())
            """
        ),
        {"id": leo_id, "email": leo_email, "password_hash": LEO_PLACEHOLDER_HASH},
    )

    for table in USER_OWNED_TABLES:
        _add_nullable_user_id(table)

    for table in USER_OWNED_TABLES:
        _backfill_user_id(table, leo_id)

    # --- Fix single-user constraints before NOT NULL / FK ---
    op.drop_constraint("entries_date_key", "entries", type_="unique")
    op.create_unique_constraint("uq_entries_user_id_date", "entries", ["user_id", "date"])

    op.drop_index("ix_health_metrics_date", table_name="health_metrics")
    op.create_unique_constraint(
        "uq_health_metrics_user_id_date", "health_metrics", ["user_id", "date"]
    )

    op.drop_constraint("uq_tracker_name", "tracker", type_="unique")
    op.create_unique_constraint("uq_tracker_user_id_name", "tracker", ["user_id", "name"])

    op.drop_constraint("pk_tracker_log", "tracker_log", type_="primary")
    op.create_primary_key("pk_tracker_log", "tracker_log", ["user_id", "tracker_id", "date"])

    op.drop_constraint("pk_treatment_log", "treatment_log", type_="primary")
    op.create_primary_key("pk_treatment_log", "treatment_log", ["user_id", "treatment_id", "date"])

    op.drop_index("ix_diet_tag_catalog_key", table_name="diet_tag_catalog")
    op.create_unique_constraint(
        "uq_diet_tag_catalog_user_id_key", "diet_tag_catalog", ["user_id", "key"]
    )

    op.drop_index("ix_supplement_catalog_key", table_name="supplement_catalog")
    op.create_unique_constraint(
        "uq_supplement_catalog_user_id_key", "supplement_catalog", ["user_id", "key"]
    )

    op.drop_index("ix_symptom_catalog_key", table_name="symptom_catalog")
    op.create_unique_constraint(
        "uq_symptom_catalog_user_id_key", "symptom_catalog", ["user_id", "key"]
    )

    op.drop_index("ix_medication_catalog_key", table_name="medication_catalog")
    op.create_unique_constraint(
        "uq_medication_catalog_user_id_key", "medication_catalog", ["user_id", "key"]
    )

    op.drop_index("ix_lab_marker_catalog_canonical_name", table_name="lab_marker_catalog")
    op.create_unique_constraint(
        "uq_lab_marker_catalog_user_id_canonical_name",
        "lab_marker_catalog",
        ["user_id", "canonical_name"],
    )

    op.drop_index("ix_lab_marker_aliases_alias", table_name="lab_marker_aliases")
    op.create_unique_constraint(
        "uq_lab_marker_aliases_user_id_alias", "lab_marker_aliases", ["user_id", "alias"]
    )

    op.drop_constraint(
        "ingredient_aliases_canonical_name_fkey", "ingredient_aliases", type_="foreignkey"
    )

    op.drop_constraint(
        "dietary_ingredients_canonical_name_key", "dietary_ingredients", type_="unique"
    )
    op.create_unique_constraint(
        "uq_dietary_ingredients_user_id_canonical_name",
        "dietary_ingredients",
        ["user_id", "canonical_name"],
    )

    op.create_foreign_key(
        "fk_ingredient_aliases_dietary_ingredient",
        "ingredient_aliases",
        "dietary_ingredients",
        ["user_id", "canonical_name"],
        ["user_id", "canonical_name"],
    )

    op.drop_constraint("uq_ingredient_aliases_alias", "ingredient_aliases", type_="unique")
    op.create_unique_constraint(
        "uq_ingredient_aliases_user_id_alias", "ingredient_aliases", ["user_id", "alias"]
    )

    op.drop_constraint("uq_embedding_source_chunk_model", "embedding", type_="unique")
    op.create_unique_constraint(
        "uq_embedding_user_source_chunk_model",
        "embedding",
        ["user_id", "source_table", "source_id", "chunk_index", "embedding_model"],
    )

    op.drop_constraint("user_settings_singleton", "user_settings", type_="check")
    op.create_unique_constraint("uq_user_settings_user_id", "user_settings", ["user_id"])

    for table in USER_OWNED_TABLES:
        _set_user_id_not_null(table)
        _add_user_fk(table)
        _add_user_id_index(table)

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_embedding() RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    VALUES (OLD.user_id, TG_TABLE_NAME, OLD.id, 'DELETE');
                ELSE
                    INSERT INTO embedding_queue (user_id, source_table, source_id, action)
                    VALUES (NEW.user_id, TG_TABLE_NAME, NEW.id, TG_OP);
                END IF;
                PERFORM pg_notify('embedding_queue', 'wake');
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_embedding() RETURNS TRIGGER AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    INSERT INTO embedding_queue (source_table, source_id, action)
                    VALUES (TG_TABLE_NAME, OLD.id, 'DELETE');
                ELSE
                    INSERT INTO embedding_queue (source_table, source_id, action)
                    VALUES (TG_TABLE_NAME, NEW.id, TG_OP);
                END IF;
                PERFORM pg_notify('embedding_queue', 'wake');
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    for table in reversed(USER_OWNED_TABLES):
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_constraint("uq_user_settings_user_id", "user_settings", type_="unique")
    op.create_check_constraint("user_settings_singleton", "user_settings", "id = 1")

    op.drop_constraint("uq_embedding_user_source_chunk_model", "embedding", type_="unique")
    op.create_unique_constraint(
        "uq_embedding_source_chunk_model",
        "embedding",
        ["source_table", "source_id", "chunk_index", "embedding_model"],
    )

    op.drop_constraint("uq_ingredient_aliases_user_id_alias", "ingredient_aliases", type_="unique")
    op.drop_constraint(
        "fk_ingredient_aliases_dietary_ingredient", "ingredient_aliases", type_="foreignkey"
    )
    op.create_unique_constraint("uq_ingredient_aliases_alias", "ingredient_aliases", ["alias"])

    op.drop_constraint(
        "uq_dietary_ingredients_user_id_canonical_name", "dietary_ingredients", type_="unique"
    )
    op.create_unique_constraint(
        "dietary_ingredients_canonical_name_key", "dietary_ingredients", ["canonical_name"]
    )
    op.create_foreign_key(
        "ingredient_aliases_canonical_name_fkey",
        "ingredient_aliases",
        "dietary_ingredients",
        ["canonical_name"],
        ["canonical_name"],
    )

    op.drop_constraint("uq_lab_marker_aliases_user_id_alias", "lab_marker_aliases", type_="unique")
    op.create_index("ix_lab_marker_aliases_alias", "lab_marker_aliases", ["alias"], unique=True)

    op.drop_constraint(
        "uq_lab_marker_catalog_user_id_canonical_name", "lab_marker_catalog", type_="unique"
    )
    op.create_index(
        "ix_lab_marker_catalog_canonical_name",
        "lab_marker_catalog",
        ["canonical_name"],
        unique=True,
    )

    op.drop_constraint("uq_medication_catalog_user_id_key", "medication_catalog", type_="unique")
    op.create_index("ix_medication_catalog_key", "medication_catalog", ["key"], unique=True)

    op.drop_constraint("uq_symptom_catalog_user_id_key", "symptom_catalog", type_="unique")
    op.create_index("ix_symptom_catalog_key", "symptom_catalog", ["key"], unique=True)

    op.drop_constraint("uq_supplement_catalog_user_id_key", "supplement_catalog", type_="unique")
    op.create_index("ix_supplement_catalog_key", "supplement_catalog", ["key"], unique=True)

    op.drop_constraint("uq_diet_tag_catalog_user_id_key", "diet_tag_catalog", type_="unique")
    op.create_index("ix_diet_tag_catalog_key", "diet_tag_catalog", ["key"], unique=True)

    op.drop_constraint("pk_treatment_log", "treatment_log", type_="primary")
    op.create_primary_key("pk_treatment_log", "treatment_log", ["treatment_id", "date"])

    op.drop_constraint("pk_tracker_log", "tracker_log", type_="primary")
    op.create_primary_key("pk_tracker_log", "tracker_log", ["tracker_id", "date"])

    op.drop_constraint("uq_tracker_user_id_name", "tracker", type_="unique")
    op.create_unique_constraint("uq_tracker_name", "tracker", ["name"])

    op.drop_constraint("uq_health_metrics_user_id_date", "health_metrics", type_="unique")
    op.create_index("ix_health_metrics_date", "health_metrics", ["date"], unique=True)

    op.drop_constraint("uq_entries_user_id_date", "entries", type_="unique")
    op.create_unique_constraint("entries_date_key", "entries", ["date"])

    op.drop_table("users")
