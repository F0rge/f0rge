import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20261001090000 extends Migration {
  override async up(): Promise<void> {
    this.addSql(`alter table "storefront_peach_payment_attempt" add column if not exists "captured_transaction_id" text null;`);
    this.addSql(`alter table "storefront_peach_payment_attempt" add column if not exists "captured_order_id" text null;`);
    this.addSql(`alter table "storefront_peach_webhook_inbox" add column if not exists "referenced_transaction_id" text null;`);
    this.addSql(`alter table "storefront_peach_webhook_inbox" add column if not exists "refund_request_id" text null;`);
    this.addSql(`create table if not exists "storefront_peach_refund_dispatch" (
      "id" text not null,
      "request_id" text not null,
      "handoff_id" text null,
      "external_order_id" text not null,
      "original_transaction_id" text not null,
      "amount_minor" numeric not null,
      "raw_amount_minor" jsonb not null,
      "currency_code" text not null,
      "cancel_order" boolean not null default false,
      "allocation" jsonb not null default '{}'::jsonb,
      "status" text not null,
      "firstout_status" text null,
      "provider_refund_id" text null,
      "provider_result_code" text null,
      "canonical_sha256" text null,
      "medusa_payment_id" text null,
      "medusa_refund_id" text null,
      "authorization_key" text null,
      "created_at" timestamptz not null default now(),
      "updated_at" timestamptz not null default now(),
      "deleted_at" timestamptz null,
      constraint "storefront_peach_refund_dispatch_pkey" primary key ("id")
    );`);
    this.addSql(`create unique index if not exists "IDX_storefront_peach_refund_dispatch_request_id_unique" on "storefront_peach_refund_dispatch" ("request_id") where deleted_at is null;`);
    this.addSql(`create unique index if not exists "IDX_storefront_peach_refund_dispatch_provider_refund_id_unique" on "storefront_peach_refund_dispatch" ("provider_refund_id") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_storefront_peach_refund_dispatch_deleted_at" on "storefront_peach_refund_dispatch" ("deleted_at") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_storefront_peach_refund_dispatch_capture" on "storefront_peach_refund_dispatch" ("original_transaction_id") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_storefront_peach_refund_dispatch_status" on "storefront_peach_refund_dispatch" ("status") where deleted_at is null;`);
    this.addSql(`create index if not exists "IDX_storefront_peach_payment_attempt_captured_transaction_id" on "storefront_peach_payment_attempt" ("captured_transaction_id") where deleted_at is null and captured_transaction_id is not null;`);
    this.addSql(`create index if not exists "IDX_storefront_peach_payment_attempt_captured_order_id" on "storefront_peach_payment_attempt" ("captured_order_id") where deleted_at is null and captured_order_id is not null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop table if exists "storefront_peach_refund_dispatch" cascade;`);
    this.addSql(`alter table if exists "storefront_peach_webhook_inbox" drop column if exists "referenced_transaction_id";`);
    this.addSql(`alter table if exists "storefront_peach_webhook_inbox" drop column if exists "refund_request_id";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop column if exists "captured_transaction_id";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop column if exists "captured_order_id";`);
  }
}
