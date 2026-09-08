"""B1 category CoA accounts, maps, and account tax_treatment.

Revision ID: 023_category_coa
Revises: 022_manual_journals
Create Date: 2026-09-01

"""

from __future__ import annotations

import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "023_category_coa"
down_revision: Union[str, Sequence[str], None] = "022_manual_journals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORY_ACCOUNTS = (
    ("4010", "Sales – Seating", "income"),
    ("4020", "Sales – Tables", "income"),
    ("4030", "Sales – Storage", "income"),
    ("4040", "Sales – Decor", "income"),
    ("4050", "Sales – Bedroom", "income"),
    ("4060", "Sales – Dining", "income"),
    ("4070", "Sales – Outdoor", "income"),
    ("5010", "COGS – Seating", "expense"),
    ("5020", "COGS – Tables", "expense"),
    ("5030", "COGS – Storage", "expense"),
    ("5040", "COGS – Decor", "expense"),
    ("5050", "COGS – Bedroom", "expense"),
    ("5060", "COGS – Dining", "expense"),
    ("5070", "COGS – Outdoor", "expense"),
    ("5110", "Stock adj – Seating", "expense"),
    ("5120", "Stock adj – Tables", "expense"),
    ("5130", "Stock adj – Storage", "expense"),
    ("5140", "Stock adj – Decor", "expense"),
    ("5150", "Stock adj – Bedroom", "expense"),
    ("5160", "Stock adj – Dining", "expense"),
    ("5170", "Stock adj – Outdoor", "expense"),
    ("5210", "Count var – Seating", "expense"),
    ("5220", "Count var – Tables", "expense"),
    ("5230", "Count var – Storage", "expense"),
    ("5240", "Count var – Decor", "expense"),
    ("5250", "Count var – Bedroom", "expense"),
    ("5260", "Count var – Dining", "expense"),
    ("5270", "Count var – Outdoor", "expense"),
)

CATEGORY_MAPS = (
    ("Seating", "4010", "5010", "5110", "5210"),
    ("Tables", "4020", "5020", "5120", "5220"),
    ("Storage", "4030", "5030", "5130", "5230"),
    ("Decor", "4040", "5040", "5140", "5240"),
    ("Bedroom", "4050", "5050", "5150", "5250"),
    ("Dining", "4060", "5060", "5160", "5260"),
    ("Outdoor", "4070", "5070", "5170", "5270"),
)


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "tax_treatment",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
    )
    op.execute(
        sa.text("UPDATE accounts SET tax_treatment = 'vat15' WHERE type IN ('income', 'expense')")
    )
    op.create_check_constraint(
        "ck_accounts_tax_treatment",
        "accounts",
        "tax_treatment IN ('none', 'vat15')",
    )

    conn = op.get_bind()
    now = datetime.datetime.utcnow()
    existing_codes = {
        row[0] for row in conn.execute(sa.text("SELECT code FROM accounts")).fetchall()
    }
    accounts = sa.table(
        "accounts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("is_archived", sa.Boolean),
        sa.column("tax_treatment", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    to_insert = [
        {
            "id": uuid.uuid4(),
            "code": code,
            "name": name,
            "type": account_type,
            "is_system": True,
            "is_archived": False,
            "tax_treatment": "vat15",
            "created_at": now,
            "updated_at": now,
        }
        for code, name, account_type in CATEGORY_ACCOUNTS
        if code not in existing_codes
    ]
    if to_insert:
        op.bulk_insert(accounts, to_insert)

    op.create_table(
        "category_account_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("sales_code", sa.String(length=16), nullable=False),
        sa.Column("cogs_code", sa.String(length=16), nullable=False),
        sa.Column("stock_adj_code", sa.String(length=16), nullable=False),
        sa.Column("count_var_code", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_category_account_maps"),
        sa.UniqueConstraint("category", name="uq_category_account_maps_category"),
    )

    maps = sa.table(
        "category_account_maps",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("category", sa.String),
        sa.column("sales_code", sa.String),
        sa.column("cogs_code", sa.String),
        sa.column("stock_adj_code", sa.String),
        sa.column("count_var_code", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        maps,
        [
            {
                "id": uuid.uuid4(),
                "category": category,
                "sales_code": sales_code,
                "cogs_code": cogs_code,
                "stock_adj_code": stock_adj_code,
                "count_var_code": count_var_code,
                "created_at": now,
                "updated_at": now,
            }
            for category, sales_code, cogs_code, stock_adj_code, count_var_code in CATEGORY_MAPS
        ],
    )


def downgrade() -> None:
    op.drop_table("category_account_maps")
    op.drop_constraint("ck_accounts_tax_treatment", "accounts", type_="check")
    op.drop_column("accounts", "tax_treatment")
