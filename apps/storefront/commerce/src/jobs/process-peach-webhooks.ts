import type { MedusaContainer } from "@medusajs/framework/types";
import { peachPaymentEnabled } from "../peach-payment-config";
import { syncStorefrontPeachRefundCommands } from "../storefront-peach-refunds";
import { processNextPeachWebhook, reconcilePeachCheckoutStatuses } from "../peach-webhook-processing";

function safeCode(value: unknown): string {
  return typeof value === "string" && /^[A-Za-z0-9_.-]{1,80}$/.test(value) ? value : "refund_command_sync_failed";
}

export default async function processPeachWebhooksJob(
  container: MedusaContainer,
  fetcher: typeof fetch = fetch,
): Promise<void> {
  if (!peachPaymentEnabled()) return;
  await reconcilePeachCheckoutStatuses(container);
  try {
    await syncStorefrontPeachRefundCommands(container, fetcher);
  } catch (error) {
    // A Firstout refund-feed outage cannot block already-persisted Peach
    // checkout callbacks from completing their independent durable path.
    console.warn("Storefront Peach refund command sync deferred", {
      failure: safeCode(error instanceof Error ? error.message : ""),
    });
  }
  for (let processed = 0; processed < 50; processed += 1) {
    if (!await processNextPeachWebhook(container)) return;
  }
}

export const config = { name: "process-storefront-peach-webhooks", schedule: "* * * * *" };
