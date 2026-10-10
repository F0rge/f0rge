import { createHash } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import type { MedusaContainer } from "@medusajs/framework/types";
import {
  addShippingMethodToCartWorkflow,
  createPaymentCollectionForCartWorkflow,
  createPaymentSessionsWorkflow,
  updateCartWorkflow,
} from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import { checkoutHoldForCart, withCheckoutInventoryLock } from "../../../../../checkout-holds";
import { deliveryZoneForAddress, deliveryZones } from "../../../../../delivery-zones";
import { peachPaymentEnabled, PEACH_PAYMENT_PROVIDER_ID } from "../../../../../peach-payment-config";
import { updateStorefrontCheckoutContact } from "../../../../../storefront-checkout-contact";
import { testPaymentEnabled } from "../../../../../test-payment-config";

type FulfillmentType = "delivery" | "collection";
type CheckoutInput = {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  fulfillment_type: FulfillmentType;
  address_1: string;
  address_2: string;
  city: string;
  province: string;
  postal_code: string;
};

function checkoutInput(value: unknown): CheckoutInput {
  if (!value || typeof value !== "object") throw new MedusaError(MedusaError.Types.INVALID_DATA, "Enter your checkout details");
  const input = value as Record<string, unknown>;
  const fulfillmentType = input.fulfillment_type;
  if (fulfillmentType !== "delivery" && fulfillmentType !== "collection") {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Choose delivery or collection");
  }
  const strings = ["email", "first_name", "last_name", "phone", ...(fulfillmentType === "delivery"
    ? ["address_1", "address_2", "city", "province", "postal_code"] : [])];
  for (const field of strings) {
    if (typeof input[field] !== "string" || !input[field].trim() || input[field].length > 250) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, `Enter a valid ${field.replaceAll("_", " ")}`);
    }
  }
  const email = (input.email as string).trim().toLocaleLowerCase("en-ZA");
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Enter a valid email address");
  }
  return {
    email,
    first_name: (input.first_name as string).trim(),
    last_name: (input.last_name as string).trim(),
    phone: (input.phone as string).trim(),
    fulfillment_type: fulfillmentType,
    address_1: typeof input.address_1 === "string" ? input.address_1.trim() : "",
    address_2: typeof input.address_2 === "string" ? input.address_2.trim() : "",
    city: typeof input.city === "string" ? input.city.trim() : "",
    province: typeof input.province === "string" ? input.province.trim() : "",
    postal_code: typeof input.postal_code === "string" ? input.postal_code.trim() : "",
  };
}

async function existingPaymentSession(container: MedusaContainer, cartId: string): Promise<Record<string, unknown> | undefined> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: links } = await query.graph({ entity: "cart_payment_collection", fields: ["payment_collection_id"], filters: { cart_id: cartId } });
  const collectionId = links[0]?.payment_collection_id as string | undefined;
  if (!collectionId) return undefined;
  const { data: sessions } = await query.graph({
    entity: "payment_session",
    fields: ["id", "status", "amount", "currency_code", "provider_id", "data"],
    filters: { payment_collection_id: collectionId },
  });
  return sessions[0] as Record<string, unknown> | undefined;
}

function checkoutSessionStatus(session: Record<string, unknown>): string {
  const peachStatus = (session.data as Record<string, unknown> | undefined)?.peach_status;
  if (peachStatus === "initiation_unknown" || peachStatus === "unknown") return "unknown";
  if (peachStatus === "declined") return "declined";
  if (peachStatus === "cancelled") return "cancelled";
  if (peachStatus === "paid" || peachStatus === "captured") return "captured";
  return typeof session.status === "string" ? session.status : "unknown";
}

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  try {
    const peachEnabled = peachPaymentEnabled();
    const providerId = peachEnabled ? PEACH_PAYMENT_PROVIDER_ID
      : testPaymentEnabled() ? "pp_storefront-test_local" : "";
    if (!providerId) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, "Checkout is not available here");
    const input = checkoutInput(req.body);
    const accessToken = (req.body as Record<string, unknown>).confirmation_token;
    if (typeof accessToken !== "string" || !/^[A-Za-z0-9_-]{40,100}$/.test(accessToken)) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "The private order confirmation token is missing");
    }
    if (input.fulfillment_type === "delivery") {
      const zone = deliveryZoneForAddress({
        province: input.province,
        city: input.city,
        address_2: input.address_2,
        postal_code: input.postal_code,
      }, deliveryZones());
      if (!zone) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Delivery is not available for this Gauteng address");
    }

    const result = await withCheckoutInventoryLock(req.scope, async () => {
      const cartId = req.params.id;
      const query = req.scope.resolve(ContainerRegistrationKeys.QUERY);
      const { data: completedOrders } = await query.graph({
        entity: "order_cart", fields: ["order_id"], filters: { cart_id: cartId },
      });
      if (completedOrders.length) {
        throw new MedusaError(MedusaError.Types.CONFLICT, "This bag has already been checked out");
      }
      const hold = await checkoutHoldForCart(req.scope, cartId);
      if (!hold.ready) return { review: hold.changes };

      const { data: carts } = await query.graph({
        entity: "cart",
        fields: ["id", "email", "customer_id", "metadata", "total", "currency_code", "payment_collection.payment_sessions.id"],
        filters: { id: cartId },
      });
      const cart = carts[0] as { id: string; email?: string; customer_id?: string | null; metadata?: Record<string, unknown> | null; total?: number; currency_code: string } | undefined;
      if (!cart) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
      const confirmationDigest = createHash("sha256").update(accessToken).digest("hex");
      const checkoutFingerprint = createHash("sha256").update(JSON.stringify([
        input.email, input.first_name, input.last_name, input.phone, input.fulfillment_type,
        input.address_1, input.address_2, input.city, input.province, input.postal_code,
      ])).digest("hex");
      const previousDigest = cart.metadata?.storefront_confirmation_sha256;
      if (previousDigest && previousDigest !== confirmationDigest) {
        throw new MedusaError(MedusaError.Types.CONFLICT, "This bag already has a private confirmation capability");
      }
      const existingSession = await existingPaymentSession(req.scope, cartId);
      if (existingSession) {
        if (existingSession.provider_id !== providerId) {
          throw new MedusaError(MedusaError.Types.CONFLICT, "This bag already has a payment attempt. Do not start a second provider session; return to its private confirmation page for status.");
        }
        if (cart.metadata?.storefront_checkout_sha256 !== checkoutFingerprint) {
          throw new MedusaError(MedusaError.Types.CONFLICT, "This payment attempt is already prepared. Start a new bag to change checkout details.");
        }
        return {
          review: null,
          session_id: existingSession.id,
          status: checkoutSessionStatus(existingSession),
          amount: existingSession.amount,
          currency_code: existingSession.currency_code,
          provider_id: providerId,
          redirect_url: typeof (existingSession.data as Record<string, unknown> | undefined)?.redirect_url === "string"
            ? (existingSession.data as Record<string, unknown>).redirect_url : null,
          fulfillment_type: input.fulfillment_type,
          hold_expires_at: hold.expires_at,
        };
      }

      const deliveryAddress = input.fulfillment_type === "collection" ? {
        first_name: input.first_name,
        last_name: input.last_name,
        address_1: "Collection point details will be provided with your order confirmation",
        city: "Johannesburg",
        province: "Gauteng",
        country_code: "za",
        postal_code: "2000",
        phone: input.phone,
      } : {
        first_name: input.first_name,
        last_name: input.last_name,
        address_1: input.address_1,
        address_2: input.address_2,
        city: input.city,
        province: input.province,
        country_code: "za",
        postal_code: input.postal_code,
        phone: input.phone,
      };
      const checkoutMetadata = { ...(cart.metadata || {}) };
      delete checkoutMetadata.storefront_owner_claim;
      if (!cart.customer_id) checkoutMetadata.storefront_claimable_version = 1;
      else delete checkoutMetadata.storefront_claimable_version;
      await updateCartWorkflow(req.scope).run({ input: {
        id: cartId,
        shipping_address: deliveryAddress,
        metadata: {
          ...checkoutMetadata,
          storefront_confirmation_sha256: confirmationDigest,
          storefront_checkout_sha256: checkoutFingerprint,
          storefront_checkout: { fulfillment_type: input.fulfillment_type },
        },
      } });

      const optionName = input.fulfillment_type === "collection" ? "Collection" : "Gauteng delivery";
      const { data: options } = await query.graph({ entity: "shipping_option", fields: ["id", "name"], filters: { name: optionName } });
      const option = options[0] as { id: string; name: string } | undefined;
      if (!option) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "This fulfillment option is not configured");
      await addShippingMethodToCartWorkflow(req.scope).run({ input: {
        cart_id: cartId,
        options: [{ id: option.id }],
      } });

      await updateStorefrontCheckoutContact(req.scope, {
        id: cartId, email: input.email, customer_id: cart.customer_id || null,
      });
      const { data: collections } = await query.graph({ entity: "cart_payment_collection", fields: ["payment_collection_id"], filters: { cart_id: cartId } });
      let collectionId = collections[0]?.payment_collection_id as string | undefined;
      if (!collectionId) {
        const { result: collection } = await createPaymentCollectionForCartWorkflow(req.scope).run({ input: { cart_id: cartId } });
        collectionId = collection.id;
      }
      const { data: checkoutCarts } = await query.graph({
        entity: "cart",
        fields: ["id", "email", "customer_id", "currency_code", "total", "metadata", "items.*", "shipping_address.*", "shipping_methods.*"],
        filters: { id: cartId },
      });
      if (!checkoutCarts[0]) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
      const { result: createdSession } = await createPaymentSessionsWorkflow(req.scope).run({
        input: { payment_collection_id: collectionId, provider_id: providerId, data: {
          storefront_cart_id: cartId, storefront_checkout_snapshot: checkoutCarts[0],
        } },
      });
      const session = createdSession as unknown as Record<string, unknown>;
      const sessionData = session.data as Record<string, unknown> | undefined;
      return {
        review: null,
        session_id: session.id,
        status: checkoutSessionStatus(session),
        amount: session.amount,
        currency_code: session.currency_code,
        provider_id: providerId,
        redirect_url: typeof sessionData?.redirect_url === "string" ? sessionData.redirect_url : null,
        fulfillment_type: input.fulfillment_type,
        hold_expires_at: hold.expires_at,
      };
    });
    if (result.review) {
      res.status(409).json({ message: "Checkout changed. Review your bag before continuing.", changes: result.review });
      return;
    }
    res.status(200).json({ checkout: result });
  } catch (error) {
    const status = error instanceof MedusaError && error.type === MedusaError.Types.INVALID_DATA ? 400
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_ALLOWED ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.CONFLICT ? 409
      : 503;
    res.status(status).json({ message: error instanceof Error ? error.message : "Checkout is temporarily unavailable" });
  }
}
