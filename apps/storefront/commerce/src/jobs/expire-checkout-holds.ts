import type { MedusaContainer } from "@medusajs/framework/types";
import { expireCheckoutHolds } from "../checkout-holds";

export default async function expireCheckoutHoldsJob(container: MedusaContainer): Promise<void> {
  await expireCheckoutHolds(container);
}

export const config = { name: "expire-storefront-checkout-holds", schedule: "* * * * *" };
