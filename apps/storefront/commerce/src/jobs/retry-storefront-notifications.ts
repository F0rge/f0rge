import type { MedusaContainer } from "@medusajs/framework/types";
import { retryStorefrontOrderNotifications } from "../storefront-notifications";

export default async function retryStorefrontNotifications(container: MedusaContainer): Promise<void> {
  await retryStorefrontOrderNotifications(container);
}

export const config = {
  name: "retry-storefront-notifications",
  schedule: "* * * * *",
};
