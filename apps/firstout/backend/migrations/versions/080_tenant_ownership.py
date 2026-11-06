"""Stamp every business table and scope its natural keys to its organisation.

Revision ID: 080_tenant_ownership
Revises: 079_tenant_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from f0rge_db.rls import migration_bypass
from sqlalchemy.dialects.postgresql import UUID

revision = "080_tenant_ownership"
down_revision = "079_tenant_identity"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "accounts",
    "archive_credit_note_lines",
    "archive_credit_notes",
    "bank_import_line_allocations",
    "bank_import_lines",
    "bank_imports",
    "bank_rules",
    "bill_lines",
    "bills",
    "bin_stock",
    "books_events",
    "books_periods",
    "category_account_maps",
    "cin7_import_runs",
    "comms_messages",
    "credit_notes",
    "customer_addresses",
    "customer_contacts",
    "customer_portal_users",
    "customers",
    "deliveries",
    "delivery_lines",
    "document_sequences",
    "invoice_lines",
    "journal_entries",
    "journal_lines",
    "landing_bills",
    "layby_lines",
    "layby_payments",
    "laybys",
    "location_bins",
    "location_stock",
    "locations",
    "ops_commerce_acknowledgements",
    "ops_commerce_fulfillment_events",
    "ops_commerce_orders",
    "ops_commerce_refund_events",
    "ops_commerce_refunds",
    "payment_reminder_sends",
    "payment_terms",
    "payments",
    "pick_allocations",
    "pick_lines",
    "picks",
    "po_lines",
    "price_list_items",
    "price_lists",
    "product_group_variants",
    "product_groups",
    "proformas",
    "purchase_orders",
    "quote_lines",
    "quotes",
    "repeating_invoice_lines",
    "repeating_invoices",
    "role_permissions",
    "roles",
    "sales_order_lines",
    "sales_order_payments",
    "sales_orders",
    "sku_bom_lines",
    "sku_stock",
    "sku_supplier_prices",
    "skus",
    "stock_adjustment_lines",
    "stock_adjustments",
    "stock_return_lines",
    "stock_returns",
    "stocktake_lines",
    "stocktakes",
    "supplier_addresses",
    "supplier_contacts",
    "suppliers",
    "tax_invoices",
    "tax_rules",
    "team_settings",
    "transfer_lines",
    "transfers",
    "unit_cost_audit",
    "vat201_period_events",
    "vat201_periods",
)
ALREADY_OWNED = {"team_settings", "document_sequences"}


def _scope_keys(table: str, *, reverse: bool = False) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints(table):
        columns = constraint["column_names"]
        if reverse:
            if "team_id" not in columns:
                continue
            columns = [column for column in columns if column != "team_id"]
        elif "team_id" in columns:
            continue
        else:
            columns = ["team_id", *columns]
        op.drop_constraint(constraint["name"], table, type_="unique")
        op.create_unique_constraint(constraint["name"], table, columns)
    # pg_get_indexdef preserves predicates, expressions, ordering and operator classes.
    indexes = bind.execute(
        sa.text("""SELECT i.relname, pg_get_indexdef(i.oid)
        FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid
        JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname=current_schema() AND t.relname=:table
          AND x.indisunique AND NOT x.indisprimary
          AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid=i.oid)"""),
        {"table": table},
    ).all()
    for name, definition in indexes:
        if reverse:
            rewritten = definition.replace(" USING btree (team_id, ", " USING btree (", 1)
        else:
            if " USING btree (team_id," in definition:
                continue
            rewritten = definition.replace(" USING btree (", " USING btree (team_id, ", 1)
        if definition != rewritten:
            op.drop_index(name, table_name=table)
            bind.execute(sa.text(rewritten))


def _tenant_foreign_keys(*, reverse: bool = False) -> None:
    """UUID references must name rows in the same tenant, including raw writes."""
    import hashlib

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if reverse:
        for table in TENANT_TABLES:
            for fk in inspector.get_foreign_keys(table):
                if fk["name"].startswith("tenant_fk_"):
                    op.drop_constraint(fk["name"], table, type_="foreignkey")
        for table in TENANT_TABLES:
            for constraint in sa.inspect(bind).get_unique_constraints(table):
                if constraint["name"].startswith("tenant_ref_"):
                    op.drop_constraint(constraint["name"], table, type_="unique")
        return
    targets = set()
    for table in TENANT_TABLES:
        for fk in inspector.get_foreign_keys(table):
            target = fk["referred_table"]
            if target not in TENANT_TABLES or "team_id" in fk["constrained_columns"]:
                continue
            remote = tuple(fk["referred_columns"])
            key = (target, remote)
            suffix = hashlib.sha256(repr(key).encode()).hexdigest()[:16]
            if key not in targets:
                op.create_unique_constraint(f"tenant_ref_{suffix}", target, ["team_id", *remote])
                targets.add(key)
            suffix = hashlib.sha256(repr((table, fk["name"])).encode()).hexdigest()[:16]
            op.create_foreign_key(
                f"tenant_fk_{suffix}",
                table,
                target,
                ["team_id", *fk["constrained_columns"]],
                ["team_id", *remote],
                deferrable=True,
                initially="DEFERRED",
            )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM teams")) != 1:
        raise RuntimeError("Tenant backfill requires exactly one inventoried bootstrap team")
    for table in TENANT_TABLES:
        if table not in ALREADY_OWNED:
            op.add_column(table, sa.Column("team_id", UUID(as_uuid=True), nullable=True))
    # Transient migration-only bypass; no standing application escape hatch.
    with migration_bypass(bind, TENANT_TABLES):
        for table in TENANT_TABLES:
            if table not in ALREADY_OWNED:
                bind.execute(sa.text(f'UPDATE "{table}" SET team_id=(SELECT id FROM teams)'))
    for table in TENANT_TABLES:
        if table not in ALREADY_OWNED:
            op.alter_column(
                table,
                "team_id",
                nullable=False,
                server_default=sa.text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
            )
            op.create_foreign_key(
                f"fk_{table}_team", table, "teams", ["team_id"], ["id"], ondelete="RESTRICT"
            )
            op.create_index(f"ix_{table}_team_id", table, ["team_id"])
        _scope_keys(table)
    _tenant_foreign_keys()
    # Scoped uniqueness no longer supplies a leading sku_id lookup index.
    op.create_index("ix_sku_stock_sku_lookup", "sku_stock", ["sku_id"])


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_sku_stock_sku_lookup"))
    _tenant_foreign_keys(reverse=True)
    # Refuses safely if new tenants have duplicate natural keys: restore backup instead.
    for table in reversed(TENANT_TABLES):
        if table not in ALREADY_OWNED:
            _scope_keys(table, reverse=True)
            op.drop_index(f"ix_{table}_team_id", table_name=table)
            op.drop_constraint(f"fk_{table}_team", table, type_="foreignkey")
            op.drop_column(table, "team_id")
