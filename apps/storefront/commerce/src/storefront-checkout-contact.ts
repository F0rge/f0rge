import type { ICartModuleService, ILockingModule, MedusaContainer } from "@medusajs/framework/types";
import { MedusaError, Modules } from "@medusajs/framework/utils";
import type { FulfillmentPromiseSummary } from "./checkout-holds";

export type CheckoutQuote = {
  amount: number;
  currency_code: string;
  delivery_amount: number;
  hold_expires_at: string;
  fulfillment_promise?: FulfillmentPromiseSummary;
  items: { id: string; title: string; quantity: number; total: number }[];
  review_token: string;
};

/** Checkout contact is separate from the owner already verified by the BFF. */
export async function updateStorefrontCheckoutContact(container: MedusaContainer, input: {
  id: string; email: string; customer_id: string | null;
  checkout?: {
    confirmationDigest: string;
    fingerprint: string;
    fulfillmentType: "delivery" | "collection";
    quote: CheckoutQuote;
  };
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
    if (!input.checkout) {
      await carts.updateCarts(input.id, { email: input.email, customer_id: input.customer_id });
      return;
    }
    const metadata: Record<string, unknown> = {
      ...current.metadata,
      storefront_confirmation_sha256: input.checkout.confirmationDigest,
      storefront_checkout_sha256: input.checkout.fingerprint,
      storefront_checkout: { fulfillment_type: input.checkout.fulfillmentType },
      storefront_checkout_review: input.checkout.quote,
    };
    delete metadata.storefront_owner_claim;
    if (input.customer_id) delete metadata.storefront_claimable_version;
    else metadata.storefront_claimable_version = 1;
    await carts.updateCarts(input.id, { email: input.email, customer_id: input.customer_id, metadata });
  }, { timeout: 5, expire: 15 });
}
