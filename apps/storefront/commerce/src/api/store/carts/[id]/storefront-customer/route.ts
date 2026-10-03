import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import type { ILockingModule } from "@medusajs/framework/types";
import { updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
  const customerId = req.headers["x-storefront-customer-id"];
  if (typeof customerId !== "string" || !/^cus_[A-Za-z0-9_-]+$/.test(customerId)) {
    res.status(404).json({ message: "Bag not found" });
    return;
  }
  const cartId = req.params.id;
  try {
    const locking = req.scope.resolve(Modules.LOCKING) as ILockingModule;
    const cart = await locking.execute(`storefront-cart-owner:${cartId}`, async () => {
      const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
      const { data } = await query.graph({ entity: "cart", fields: ["id", "customer_id"], filters: { id: cartId } });
      const current = data[0] as { id: string; customer_id?: string | null } | undefined;
      if (!current || (current.customer_id && current.customer_id !== customerId)) {
        throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
      }
      const { data: existingOrders } = await query.graph({ entity: "order_cart", fields: ["order_id"], filters: { cart_id: cartId } });
      if (existingOrders.length) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
      if (current.customer_id === customerId) return { id: current.id };
      await updateCartWorkflow(req.scope).run({ input: { id: cartId, customer_id: customerId } });
      return { id: cartId };
    }, { timeout: 5, expire: 15 });
    res.json({ cart });
  } catch {
    res.status(404).json({ message: "Bag not found" });
  }
}
