"""Channel OMS: ATP, listings, orders, outbox, Shopify clearing.

Revision ID: 053_channel_oms
Revises: 052_lookbook_events
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "053_channel_oms"
down_revision: Union[str, Sequence[str], None] = "052_lookbook_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_settings",
        sa.Column(
            "channel_atp_mode",
            sa.String(length=32),
            nullable=False,
            server_default="warehouse_only",
        ),
    )
    op.add_column(
        "team_settings",
        sa.Column(
            "channel_atp_location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_team_settings_channel_atp_mode",
        "team_settings",
        "channel_atp_mode IN ('warehouse_only', 'pooled', 'mapped')",
    )

    op.add_column(
        "tax_invoices",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="books"),
    )
    op.add_column(
        "tax_invoices",
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_tax_invoices_source",
        "tax_invoices",
        "source IN ('books', 'till', 'layby', 'shopify', 'email', 'manual')",
    )

    op.create_table(
        "sales_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("shopify_shop_domain", sa.String(length=255), nullable=True),
        sa.Column("shopify_admin_token", sa.Text(), nullable=True),
        sa.Column("shopify_webhook_secret", sa.Text(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_sales_channels_slug"),
    )
    op.create_table(
        "channel_location_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shopify_location_gid", sa.String(length=128), nullable=True),
        sa.Column("include_in_atp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("channel_id", "location_id", name="uq_channel_location_maps_pair"),
    )
    op.create_table(
        "channel_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_variant_id", sa.String(length=64), nullable=True),
        sa.Column("external_inventory_item_id", sa.String(length=128), nullable=True),
        sa.Column("external_sku", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("channel_id", "sku_id", name="uq_channel_listings_sku"),
    )
    op.create_index(
        "uq_channel_listings_variant",
        "channel_listings",
        ["channel_id", "external_variant_id"],
        unique=True,
        postgresql_where=sa.text("external_variant_id IS NOT NULL"),
    )
    op.create_table(
        "channel_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("key_hash", name="uq_channel_api_keys_hash"),
    )
    op.create_table(
        "channel_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_order_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pick_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shopify_fulfillment_order_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "allocations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invoice_id"], ["tax_invoices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pick_id"], ["picks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("channel_id", "external_order_id", name="uq_channel_orders_external"),
    )
    op.create_table(
        "channel_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("channel_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["channel_order_id"], ["channel_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="CASCADE"),
        sa.CheckConstraint("attempts >= 0", name="ck_channel_outbox_attempts"),
    )
    op.create_index("ix_channel_outbox_drain", "channel_outbox", ["status", "available_at"])


def downgrade() -> None:
    op.drop_index("ix_channel_outbox_drain", table_name="channel_outbox")
    op.drop_table("channel_outbox")
    op.drop_table("channel_orders")
    op.drop_table("channel_api_keys")
    op.drop_index("uq_channel_listings_variant", table_name="channel_listings")
    op.drop_table("channel_listings")
    op.drop_table("channel_location_maps")
    op.drop_table("sales_channels")
    op.drop_constraint("ck_tax_invoices_source", "tax_invoices", type_="check")
    op.drop_column("tax_invoices", "location_id")
    op.drop_column("tax_invoices", "source")
    op.drop_constraint("ck_team_settings_channel_atp_mode", "team_settings", type_="check")
    op.drop_column("team_settings", "channel_atp_location_id")
    op.drop_column("team_settings", "channel_atp_mode")
