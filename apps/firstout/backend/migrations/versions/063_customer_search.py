"""Customer search indexes for name, email, and normalised phone.

Revision ID: 063_customer_search
Revises: 062_cin7_import

Adds a stored national-digit phone column (0027 / 27 / leading 0 folded away)
and trigram indexes so partial name, email, and cell search stays index-backed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.customer import PHONE_NATIONAL_SQL

revision: str = "063_customer_search"
down_revision: Union[str, Sequence[str], None] = "062_cin7_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "customers",
        sa.Column(
            "phone_national",
            sa.String(length=32),
            sa.Computed(PHONE_NATIONAL_SQL, persisted=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_customers_name_trgm",
        "customers",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_customers_email_trgm",
        "customers",
        ["email"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"email": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_customers_phone_national_trgm",
        "customers",
        ["phone_national"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"phone_national": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_customers_phone_national_trgm", table_name="customers")
    op.drop_index("ix_customers_email_trgm", table_name="customers")
    op.drop_index("ix_customers_name_trgm", table_name="customers")
    op.drop_column("customers", "phone_national")
