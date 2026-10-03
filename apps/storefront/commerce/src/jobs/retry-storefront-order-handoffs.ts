import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { deliverStorefrontOrderOutbox, retryableStorefrontOutbox } from "../storefront-order-handoff";

type OrderRow = { id: string; metadata?: Record<string, unknown> | null };

export default async function retryStorefrontOrderHandoffs(container: MedusaContainer): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const now = new Date();
  const take = 100;
  let skip = 0;
  while (true) {
    const { data } = await query.graph({
      entity: "order",
      fields: ["id", "metadata"],
      pagination: { take, skip },
    });
    const orders = data as OrderRow[];
    if (!orders.length) break;
    for (const order of orders) {
      const outbox = order.metadata?.storefront_handoff_outbox;
      if (retryableStorefrontOutbox(outbox, now)) {
        await deliverStorefrontOrderOutbox(container, order.id, now);
      }
    }
    if (orders.length < take) break;
    skip += orders.length;
  }
}

export const config = {
  name: "retry-storefront-order-handoffs",
  schedule: "* * * * *",
};
