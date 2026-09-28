import type { SubscriberArgs, SubscriberConfig } from "@medusajs/framework";
import { ensureStorefrontOrderOutbox, withStorefrontOrderHandoffLock } from "../storefront-order-handoff";

export default async function storefrontOrderPlaced({ event, container }: SubscriberArgs<{ id: string }>) {
  // Persist the paid snapshot promptly. The scheduled job reserves its stock
  // commitment under the shared inventory lock and delivers it to Firstout.
  // This subscriber may run inside the local payment callback's inventory lock.
  await withStorefrontOrderHandoffLock(container, event.data.id, () =>
    ensureStorefrontOrderOutbox(container, event.data.id));
}

export const config: SubscriberConfig = { event: "order.placed" };
