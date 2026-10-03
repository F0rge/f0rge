import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { claimGuestStorefrontOrder, verifiedStorefrontCustomer } from "../../../../../../storefront-order-claims";

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
  const orderId = req.params.id;
  const customer = verifiedStorefrontCustomer((req as MedusaRequest & { auth_context?: unknown }).auth_context);
  if (!customer) {
    res.status(401).json({ message: "Verified customer sign-in is required" });
    return;
  }
  if (typeof orderId !== "string" || !/^order_[A-Za-z0-9_-]+$/.test(orderId)) {
    res.status(404).json({ message: "Order not found" });
    return;
  }
  try {
    const db = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
    const result = await claimGuestStorefrontOrder(db, orderId, customer);
    if (result === "not_available") {
      res.status(404).json({ message: "Order not found" });
      return;
    }
    res.status(200).json({ claimed: result === "claimed", already_owned: result === "already_owned" });
  } catch {
    res.status(503).json({ message: "Order could not be linked right now" });
  }
}
