"""Prepare tenant policies; activation is a separate operator cutover.

Revision ID: 081_tenant_rls
Revises: 080_tenant_ownership
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "081_tenant_rls"
down_revision = "080_tenant_ownership"
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


def upgrade() -> None:
    # Unreleased revision: routine preDeploy prepares policies only. Never gate an
    # Alembic revision with a skipped/no-op upgrade: activation is outside Alembic.
    # app.commands.tenant_cutover verifies the runtime role before ENABLE/FORCE.
    for table in TENANT_TABLES:
        condition = "team_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
        op.execute(
            sa.text(
                f'CREATE POLICY organisation_isolation ON "{table}" FOR ALL USING ({condition}) WITH CHECK ({condition})'
            )
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(sa.text(f'DROP POLICY organisation_isolation ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
