import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { listClaimableGuestOrders, verifiedStorefrontCustomer } from "../../../../../storefront-order-claims";

export async function GET(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
  const customer = verifiedStorefrontCustomer((req as MedusaRequest & { auth_context?: unknown }).auth_context);
  if (!customer) {
    res.status(401).json({ message: "Verified customer sign-in is required" });
    return;
  }
  try {
    const db = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
    const orders = await listClaimableGuestOrders(db, customer);
    res.status(200).json({ orders });
  } catch {
    res.status(503).json({ message: "Guest orders are temporarily unavailable" });
  }
}
