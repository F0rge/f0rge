import { Migration } from "@medusajs/framework/mikro-orm/migrations";
import { refundCutoverSchema } from "../schema";

export class Migration20261122153000 extends Migration {
  override async up(): Promise<void> {
    for (const statement of refundCutoverSchema) this.addSql(statement);
  }

  override async down(): Promise<void> {
    this.addSql("DROP TABLE storefront_refund_writer;");
    this.addSql("DROP TABLE storefront_refund_cutover;");
  }
}
