import type { MedusaContainer } from "@medusajs/framework/types";
import { peachPaymentEnabled } from "../peach-payment-config";
import { processNextPeachWebhook, reconcilePeachCheckoutStatuses } from "../peach-webhook-processing";

export default async function processPeachWebhooksJob(container: MedusaContainer): Promise<void> {
  if (!peachPaymentEnabled()) return;
  await reconcilePeachCheckoutStatuses(container);
  for (let processed = 0; processed < 50; processed += 1) {
    if (!await processNextPeachWebhook(container)) return;
  }
}

export const config = { name: "process-storefront-peach-webhooks", schedule: "* * * * *" };
