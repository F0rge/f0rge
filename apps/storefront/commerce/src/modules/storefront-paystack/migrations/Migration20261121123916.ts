import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20261121123916 extends Migration {

  override async up(): Promise<void> {
    this.addSql(`alter table if exists "storefront_paystack_webhook_inbox" drop constraint if exists "storefront_paystack_webhook_inbox_event_key_unique";`);
    this.addSql(`alter table if exists "storefront_paystack_refund_dispatch" drop constraint if exists "storefront_paystack_refund_dispatch_provider_refund_id_unique";`);
    this.addSql(`alter table if exists "storefront_paystack_refund_dispatch" drop constraint if exists "storefront_paystack_refund_dispatch_request_id_unique";`);
    this.addSql(`alter table if exists "storefront_paystack_payment_attempt" drop constraint if exists "storefront_paystack_payment_attempt_reference_unique";`);
    this.addSql(`alter table if exists "storefront_paystack_payment_attempt" drop constraint if exists "storefront_paystack_payment_attempt_payment_session_id_unique";`);
    this.addSql(`create table if not exists "storefront_paystack_payment_attempt" ("id" text not null, "payment_session_id" text not null, "cart_id" text null, "checkout_snapshot" jsonb null, "reference" text not null, "transaction_id" text null, "captured_order_id" text null, "amount_minor" numeric not null, "currency_code" text not null, "status" text not null, "authorization_url" text null, "last_event_timestamp" text null, "last_event_state" text null, "last_status_checked_at" timestamptz null, "raw_amount_minor" jsonb not null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "storefront_paystack_payment_attempt_pkey" primary key ("id"));`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_paystack_payment_attempt_payment_session_id_unique" ON "storefront_paystack_payment_attempt" ("payment_session_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_paystack_payment_attempt_reference_unique" ON "storefront_paystack_payment_attempt" ("reference") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_payment_attempt_deleted_at" ON "storefront_paystack_payment_attempt" ("deleted_at") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_payment_attempt_captured_order_id" ON "storefront_paystack_payment_attempt" ("captured_order_id") WHERE captured_order_id IS NOT NULL AND deleted_at IS NULL;`);

    this.addSql(`create table if not exists "storefront_paystack_refund_dispatch" ("id" text not null, "request_id" text not null, "handoff_id" text null, "external_order_id" text not null, "original_transaction_id" text not null, "amount_minor" numeric not null, "currency_code" text not null, "cancel_order" boolean not null default false, "allocation" jsonb not null default '{}', "status" text not null, "firstout_status" text null, "provider_refund_id" text null, "provider_result_code" text null, "canonical_sha256" text null, "medusa_payment_id" text null, "medusa_refund_id" text null, "authorization_key" text null, "raw_amount_minor" jsonb not null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "storefront_paystack_refund_dispatch_pkey" primary key ("id"));`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_paystack_refund_dispatch_request_id_unique" ON "storefront_paystack_refund_dispatch" ("request_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_paystack_refund_dispatch_provider_refund_id_unique" ON "storefront_paystack_refund_dispatch" ("provider_refund_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_refund_dispatch_deleted_at" ON "storefront_paystack_refund_dispatch" ("deleted_at") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_refund_dispatch_capture" ON "storefront_paystack_refund_dispatch" ("original_transaction_id") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_refund_dispatch_status" ON "storefront_paystack_refund_dispatch" ("status") WHERE deleted_at IS NULL;`);

    this.addSql(`create table if not exists "storefront_paystack_webhook_inbox" ("id" text not null, "event_key" text not null, "source" text not null, "kind" text not null, "reference" text not null, "transaction_id" text null, "provider_refund_id" text null, "refund_reference" text null, "refund_request_id" text null, "amount_minor" numeric not null, "currency_code" text not null, "provider_status" text not null, "result_state" text not null, "event_timestamp" text not null, "raw_sha256" text not null, "canonical_sha256" text not null, "signature_sha256" text null, "status" text not null, "attempt_count" integer not null, "next_attempt_at" timestamptz null, "lease_until" timestamptz null, "lease_token" text null, "last_error_code" text null, "processed_at" timestamptz null, "raw_amount_minor" jsonb not null, "created_at" timestamptz not null default now(), "updated_at" timestamptz not null default now(), "deleted_at" timestamptz null, constraint "storefront_paystack_webhook_inbox_pkey" primary key ("id"));`);
    this.addSql(`CREATE UNIQUE INDEX IF NOT EXISTS "IDX_storefront_paystack_webhook_inbox_event_key_unique" ON "storefront_paystack_webhook_inbox" ("event_key") WHERE deleted_at IS NULL;`);
    this.addSql(`CREATE INDEX IF NOT EXISTS "IDX_storefront_paystack_webhook_inbox_deleted_at" ON "storefront_paystack_webhook_inbox" ("deleted_at") WHERE deleted_at IS NULL;`);
  }

  override async down(): Promise<void> {
    this.addSql(`drop table if exists "storefront_paystack_payment_attempt" cascade;`);

    this.addSql(`drop table if exists "storefront_paystack_refund_dispatch" cascade;`);

    this.addSql(`drop table if exists "storefront_paystack_webhook_inbox" cascade;`);
  }

}
