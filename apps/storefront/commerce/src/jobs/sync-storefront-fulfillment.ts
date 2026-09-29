import type { MedusaContainer } from "@medusajs/framework/types";
import { syncStorefrontFulfillmentEvents } from "../storefront-fulfillment-events";

export default async function syncStorefrontFulfillment(container: MedusaContainer): Promise<void> {
  await syncStorefrontFulfillmentEvents(container);
}

export const config = {
  name: "sync-storefront-fulfillment-events",
  schedule: "* * * * *",
};
