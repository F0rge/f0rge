import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20260930180331 extends Migration {

  override async up(): Promise<void> {
    this.addSql(`alter table if exists "storefront_peach_webhook_inbox" drop constraint if exists "storefront_peach_webhook_inbox_webhook_id_unique";`);
    this.addSql(`alter table if exists "storefront_peach_webhook_inbox" drop constraint if exists "storefront_peach_webhook_inbox_event_key_unique";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop constraint if exists "storefront_peach_payment_attempt_checkout_id_unique";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop constraint if exists "storefront_peach_payment_attempt_nonce_unique";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop constraint if exists "storefront_peach_payment_attempt_merchant_reference_unique";`);
    this.addSql(`alter table if exists "storefront_peach_payment_attempt" drop constraint if exists "storefront_peach_payment_attempt_payment_session_id_unique";`);
    this.addSql(`create table if not exists "storefront_peach_payment_attempt" ("id" text not null, "payment_session_id" text not null, "merchant_reference" text not null, "nonce" text not null, "checkout_id" text null, "amount_minor" numeric not null, "raw_amount_minor" jsonb not null, "currency_code" text not null, "status" text not null, "redirect_url" text null, "last_event_timestamp" text null, "last_event_state" text null, "last_status_checked_at" timestamptz null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "storefront_peach_payment_attempt_pkey" primary key ("id"));`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_payment_attempt_payment_session_id_unique" ON "storefront_peach_payment_attempt" ("payment_session_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_payment_attempt_merchant_reference_unique" ON "storefront_peach_payment_attempt" ("merchant_reference") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_payment_attempt_nonce_unique" ON "storefront_peach_payment_attempt" ("nonce") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_payment_attempt_checkout_id_unique" ON "storefront_peach_payment_attempt" ("checkout_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_peach_payment_attempt_deleted_at" ON "storefront_peach_payment_attempt" ("deleted_at") WHERE deleted_at IS NULL;`);

    this.addSql(`create table if not exists "storefront_peach_webhook_inbox" ("id" text not null, "event_key" text not null, "source" text not null, "webhook_id" text null, "checkout_id" text not null, "merchant_reference" text not null, "amount_minor" numeric not null, "raw_amount_minor" jsonb not null, "currency_code" text not null, "payment_type" text not null, "result_code" text not null, "transaction_id" text null, "event_timestamp" text not null, "result_state" text not null, "raw_sha256" text not null, "canonical_sha256" text not null, "signature_sha256" text null, "status" text not null, "attempt_count" integer not null, "next_attempt_at" timestamptz null, "lease_until" timestamptz null, "lease_token" text null, "last_error_code" text null, "processed_at" timestamptz null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "storefront_peach_webhook_inbox_pkey" primary key ("id"));`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_webhook_inbox_event_key_unique" ON "storefront_peach_webhook_inbox" ("event_key") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_peach_webhook_inbox_webhook_id_unique" ON "storefront_peach_webhook_inbox" ("webhook_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_peach_webhook_inbox_deleted_at" ON "storefront_peach_webhook_inbox" ("deleted_at") WHERE deleted_at IS NULL;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop table if exists "storefront_peach_payment_attempt" cascade;`);

    this.addSql(`drop table if exists "storefront_peach_webhook_inbox" cascade;`);
  }

}
