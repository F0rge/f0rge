import type { MedusaContainer } from "@medusajs/framework/types";
import { paystackPaymentEnabled } from "../paystack-payment-config";
import { syncStorefrontPaystackRefundCommands } from "../storefront-paystack-refunds";
import { processNextPaystackObservation, reconcilePaystackCheckoutStatuses } from "../paystack-webhook-processing";

function safeCode(value: unknown): string {
  return typeof value === "string" && /^[A-Za-z0-9_.-]{1,80}$/.test(value) ? value : "refund_command_sync_failed";
}

export default async function processPaystackWebhooksJob(
  container: MedusaContainer,
  fetcher: typeof fetch = fetch,
): Promise<void> {
  if (!paystackPaymentEnabled()) return;
  await reconcilePaystackCheckoutStatuses(container, undefined, fetcher);
  try {
    await syncStorefrontPaystackRefundCommands(container, fetcher);
  } catch (error) {
    // A Firstout refund-feed outage cannot block already-persisted Paystack
    // observations from completing their independent durable path.
    console.warn("Storefront Paystack refund command sync deferred", {
      failure: safeCode(error instanceof Error ? error.message : ""),
    });
  }
  for (let processed = 0; processed < 50; processed += 1) {
    if (!await processNextPaystackObservation(container)) return;
  }
}

export const config = { name: "process-storefront-paystack-webhooks", schedule: "* * * * *" };
