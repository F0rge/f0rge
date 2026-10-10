import type { ICartModuleService, ILockingModule, MedusaContainer } from "@medusajs/framework/types";
import { MedusaError, Modules } from "@medusajs/framework/utils";

/** Checkout contact is separate from the owner already verified by the BFF. */
export async function updateStorefrontCheckoutContact(container: MedusaContainer, input: {
  id: string; email: string; customer_id: string | null;
}): Promise<void> {
  const locking = container.resolve<ILockingModule>(Modules.LOCKING);
  await locking.execute(`storefront-cart-owner:${input.id}`, async () => {
    const carts = container.resolve<ICartModuleService>(Modules.CART);
    const current = await carts.retrieveCart(input.id);
    if ((current.customer_id || null) !== input.customer_id) {
      throw new MedusaError(MedusaError.Types.CONFLICT, "Bag ownership changed. Reload the bag before checking out.");
    }
    // Native update-cart(email) infers account ownership from an unverified
    // contact address. Keep the already authorized owner, including null guests.
    await carts.updateCarts(input.id, { email: input.email, customer_id: input.customer_id });
  }, { timeout: 5, expire: 15 });
}
