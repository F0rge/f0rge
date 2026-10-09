import { Migration } from "@medusajs/framework/mikro-orm/migrations";

export class Migration20261009120000 extends Migration {
  override async up(): Promise<void> {
    this.addSql(`alter table "storefront_peach_payment_attempt" add column if not exists "cart_id" text null;`);
    this.addSql(`alter table "storefront_peach_payment_attempt" add column if not exists "checkout_snapshot" jsonb null;`);
  }

  override async down(): Promise<void> {
    this.addSql(`alter table "storefront_peach_payment_attempt" drop column if exists "checkout_snapshot";`);
    this.addSql(`alter table "storefront_peach_payment_attempt" drop column if exists "cart_id";`);
  }
}
