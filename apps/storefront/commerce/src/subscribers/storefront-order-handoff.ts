import type { SubscriberArgs, SubscriberConfig } from "@medusajs/framework";
import { ensureStorefrontOrderOutbox, withStorefrontOrderHandoffLock } from "../storefront-order-handoff";
import { ensureStorefrontOrderNotificationOutbox } from "../storefront-notifications";

export default async function storefrontOrderPlaced({ event, container }: SubscriberArgs<{ id: string }>) {
  // Persist the paid snapshot promptly. The scheduled job reserves its stock
  // commitment under the shared inventory lock and delivers it to Firstout.
  // This subscriber may run inside the local payment callback's inventory lock.
  await withStorefrontOrderHandoffLock(container, event.data.id, async () => {
    await ensureStorefrontOrderOutbox(container, event.data.id);
    await ensureStorefrontOrderNotificationOutbox(container, event.data.id);
  });
}

export const config: SubscriberConfig = { event: "order.placed" };
