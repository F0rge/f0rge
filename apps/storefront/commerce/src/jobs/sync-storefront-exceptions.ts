import type { MedusaContainer } from "@medusajs/framework/types";
import { syncStorefrontExceptions } from "../storefront-exception-worker";

export default async function syncStorefrontExceptionJob(container: MedusaContainer): Promise<void> {
  // Native integration runners inherit shell credentials but use empty disposable
  // databases. They must never publish a complete scan for the live company.
  if (process.env.NODE_ENV === "test") return;
  if (!process.env.FIRSTOUT_OPS_URL || !process.env.FIRSTOUT_OPS_TOKEN || !process.env.FIRSTOUT_OPS_COMPANY_ID) return;
  await syncStorefrontExceptions(container);
}
export const config = { name: "sync-storefront-live-exceptions", schedule: "* * * * *" };
