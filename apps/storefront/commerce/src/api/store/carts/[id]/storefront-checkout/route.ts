import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import type { MedusaContainer } from "@medusajs/framework/types";
import {
  addShippingMethodToCartWorkflow,
  createPaymentCollectionForCartWorkflow,
  createPaymentSessionsWorkflow,
  updateCartWorkflow,
} from "@medusajs/medusa/core-flows";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import { checkoutHoldForCart, withCheckoutInventoryLock, type FulfillmentPromiseSummary } from "../../../../../checkout-holds";
import { deliveryZoneForAddress, deliveryZones } from "../../../../../delivery-zones";
import { medusaAmountToMinor, minorToMajor } from "../../../../../paystack-checkout";
import { paystackPaymentEnabled, PAYSTACK_PAYMENT_PROVIDER_ID } from "../../../../../paystack-payment-config";
import { updateStorefrontCheckoutContact, type CheckoutQuote } from "../../../../../storefront-checkout-contact";
import { clearCheckoutShippingWorkflow } from "../../../../../storefront-checkout-shipping";
import { testPaymentEnabled } from "../../../../../test-payment-config";

type FulfillmentType = "delivery" | "collection";
type CheckoutCart = {
  id: string;
  customer_id?: string | null;
  metadata?: Record<string, unknown> | null;
  total: unknown;
  shipping_total: unknown;
  currency_code: string;
  items?: { id: string; title: string; variant_id: string; quantity: number; unit_price: unknown; total: unknown }[];
  shipping_methods?: { id: string; shipping_option_id: string }[];
};
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
  const paystackStatus = (session.data as Record<string, unknown> | undefined)?.paystack_status;
  if (paystackStatus === "initiation_unknown" || paystackStatus === "unknown") return "unknown";
  if (paystackStatus === "declined") return "declined";
  if (paystackStatus === "paid" || paystackStatus === "captured") return "captured";
  return typeof session.status === "string" ? session.status : "unknown";
}

async function readCheckoutCart(container: MedusaContainer, cartId: string): Promise<CheckoutCart> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data: carts } = await query.graph({
    entity: "cart",
    fields: ["id", "email", "customer_id", "currency_code", "total", "shipping_total", "metadata", "items.*", "items.total", "shipping_address.*", "shipping_methods.*"],
    filters: { id: cartId },
  });
  const cart = carts[0] as CheckoutCart | undefined;
  if (!cart) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
  return cart;
}

function quoteForCart(
  cart: CheckoutCart,
  fingerprint: string,
  hold: { expires_at?: string; fulfillment_promise?: FulfillmentPromiseSummary },
  reviewedMethods = cart.shipping_methods?.map((method) => method.id).sort() ?? [],
): CheckoutQuote {
  const expiresAt = hold.expires_at;
  const amount = medusaAmountToMinor(cart.total);
  const delivery = medusaAmountToMinor(cart.shipping_total);
  if (amount === null || delivery === null || !cart.currency_code || !expiresAt || !cart.items?.length) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Your order total could not be verified");
  }
  const secret = process.env.STOREFRONT_BFF_SECRET;
  if (!secret || secret.length < 32) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Checkout is temporarily unavailable");
  }
  const items = cart.items.map((item) => {
    const total = medusaAmountToMinor(item.total);
    if (total === null || !item.title) {
      throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Your order details could not be verified");
    }
    return { id: item.id, title: item.title, quantity: item.quantity, total: minorToMajor(total) };
  });
  const itemDetails = [...cart.items].sort((left, right) => left.id.localeCompare(right.id)).map((item) =>
    [item.id, item.title, item.variant_id, item.quantity, medusaAmountToMinor(item.unit_price), medusaAmountToMinor(item.total)]);
  const options = cart.shipping_methods?.map((method) => method.shipping_option_id).sort() ?? [];
  const reviewToken = createHmac("sha256", secret).update(JSON.stringify([
    "storefront-checkout-review-v1", cart.id, cart.customer_id ?? null, fingerprint, expiresAt,
    hold.fulfillment_promise ?? null, itemDetails, options, reviewedMethods,
    cart.currency_code, amount, delivery,
  ])).digest("hex");
  return {
    amount: minorToMajor(amount), currency_code: cart.currency_code, delivery_amount: minorToMajor(delivery),
    hold_expires_at: expiresAt, fulfillment_promise: hold.fulfillment_promise, items, review_token: reviewToken,
  };
}

function matchesReviewToken(expected: string, supplied: unknown): boolean {
  return typeof supplied === "string" && /^[a-f0-9]{64}$/.test(supplied) &&
    /^[a-f0-9]{64}$/.test(expected) && timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(supplied, "hex"));
}

function sessionCheckout(session: Record<string, unknown>, providerId: string, fulfillmentType: FulfillmentType, expiresAt: string | undefined) {
  const data = session.data as Record<string, unknown> | undefined;
  return {
    review: null,
    session_id: session.id,
    status: checkoutSessionStatus(session),
    amount: session.amount,
    currency_code: session.currency_code,
    provider_id: providerId,
    redirect_url: typeof data?.redirect_url === "string" ? data.redirect_url : null,
    fulfillment_type: fulfillmentType,
    hold_expires_at: expiresAt,
  };
}

export async function POST(req: MedusaRequest, res: MedusaResponse): Promise<void> {
  res.setHeader("Cache-Control", "private, no-store, max-age=0");
  try {
    const providerId = paystackPaymentEnabled() ? PAYSTACK_PAYMENT_PROVIDER_ID
      : testPaymentEnabled() ? "pp_storefront-test_local" : "";
    if (!providerId) {
      // Stable code for the storefront: it releases the checkout hold and offers the showroom instead.
      res.status(404).json({ code: "payment_unavailable", message: "Checkout is not available here" });
      return;
    }
    const input = checkoutInput(req.body);
    const { step, confirmation_token: accessToken, review_token: reviewToken } = req.body as Record<string, unknown>;
    if (step !== undefined && step !== "review" && step !== "payment") {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Choose a checkout step");
    }
    const confirmationDigest = typeof accessToken === "string" && /^[A-Za-z0-9_-]{40,100}$/.test(accessToken)
      ? createHash("sha256").update(accessToken).digest("hex") : null;
    if (step !== "review" && !confirmationDigest) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "The private order confirmation token is missing");
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
      if (!hold.ready) return { kind: "hold-changed", changes: hold.changes } as const;

      const cart = await readCheckoutCart(req.scope, cartId);
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
        // A client loaded before the release can resume an existing session.
        if (step !== undefined) {
          const savedQuote = cart.metadata?.storefront_checkout_review as CheckoutQuote | undefined;
          const quote = savedQuote ?? quoteForCart(cart, checkoutFingerprint, hold);
          if (medusaAmountToMinor(quote.amount) !== medusaAmountToMinor(existingSession.amount) ||
              quote.currency_code !== existingSession.currency_code) {
            throw new MedusaError(MedusaError.Types.CONFLICT, "This bag already has a payment attempt. Return to its private confirmation page for status.");
          }
          if (step === "review") {
            return { kind: "review", quote: { ...quote, hold_expires_at: hold.expires_at ?? quote.hold_expires_at } } as const;
          }
          if (!matchesReviewToken(quote.review_token, reviewToken)) return { kind: "quote-changed" } as const;
        }
        return { kind: "checkout", checkout: sessionCheckout(existingSession, providerId, input.fulfillment_type, hold.expires_at) } as const;
      }
      let reviewedMethods: string[] | undefined;
      if (step !== "review") {
        if (step !== "payment" || !confirmationDigest || !cart.shipping_methods?.length ||
            !matchesReviewToken(quoteForCart(cart, checkoutFingerprint, hold).review_token, reviewToken)) {
          return { kind: "quote-changed" } as const;
        }
        // Repricing replaces the methods. Compare the result against the
        // methods the customer actually reviewed before creating a payment.
        reviewedMethods = cart.shipping_methods.map((method) => method.id).sort();
      }
      if (input.fulfillment_type === "delivery" && !deliveryZoneForAddress(input, deliveryZones())) {
        throw new MedusaError(MedusaError.Types.INVALID_DATA, "Delivery is not available for this Gauteng address");
      }

      const deliveryAddress = input.fulfillment_type === "collection" ? {
        first_name: input.first_name,
        last_name: input.last_name,
        address_1: "32 4th Street",
        address_2: "Wynberg",
        city: "Sandton",
        province: "Gauteng",
        country_code: "za",
        postal_code: "2090",
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
      const optionName = input.fulfillment_type === "collection" ? "Collection" : "Gauteng delivery";
      const { data: options } = await query.graph({ entity: "shipping_option", fields: ["id", "name"], filters: { name: optionName } });
      const option = options[0] as { id: string; name: string } | undefined;
      if (!option) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "This fulfillment option is not configured");

      // Medusa otherwise reprices the old shipping option against the new
      // address. The previous zone can reject a valid address correction.
      if (cart.shipping_methods?.length) {
        await clearCheckoutShippingWorkflow(req.scope).run({
          input: { shipping_method_ids: cart.shipping_methods.map((method) => method.id) },
        });
      }
      await updateCartWorkflow(req.scope).run({ input: { id: cartId, shipping_address: deliveryAddress } });
      await addShippingMethodToCartWorkflow(req.scope).run({ input: { cart_id: cartId, options: [{ id: option.id }] } });

      const quotedCart = await readCheckoutCart(req.scope, cartId);
      const quote = quoteForCart(quotedCart, checkoutFingerprint, hold, reviewedMethods);
      if (step === "review") return { kind: "review", quote } as const;
      if (!confirmationDigest || !matchesReviewToken(quote.review_token, reviewToken)) return { kind: "quote-changed" } as const;

      const { data: collections } = await query.graph({ entity: "cart_payment_collection", fields: ["payment_collection_id"], filters: { cart_id: cartId } });
      let collectionId = collections[0]?.payment_collection_id as string | undefined;
      if (!collectionId) {
        const { result: collection } = await createPaymentCollectionForCartWorkflow(req.scope).run({ input: { cart_id: cartId } });
        collectionId = collection.id;
      }
      const { data: [paymentCollection] } = await query.graph({
        entity: "payment_collection", fields: ["amount", "currency_code"], filters: { id: collectionId },
      });
      if (!paymentCollection || medusaAmountToMinor(paymentCollection.amount) !== medusaAmountToMinor(quote.amount) ||
          paymentCollection.currency_code !== quote.currency_code) {
        return { kind: "quote-changed" } as const;
      }
      await updateStorefrontCheckoutContact(req.scope, {
        id: cartId, email: input.email, customer_id: cart.customer_id || null,
        checkout: { confirmationDigest, fingerprint: checkoutFingerprint, fulfillmentType: input.fulfillment_type, quote },
      });
      const checkoutSnapshot = await readCheckoutCart(req.scope, cartId);
      if (!matchesReviewToken(quoteForCart(checkoutSnapshot, checkoutFingerprint, hold, reviewedMethods).review_token, reviewToken)) {
        return { kind: "quote-changed" } as const;
      }
      const { result: createdSession } = await createPaymentSessionsWorkflow(req.scope).run({
        input: { payment_collection_id: collectionId, provider_id: providerId, data: {
          storefront_cart_id: cartId, storefront_checkout_snapshot: checkoutSnapshot,
          // Paystack requires the customer's email to initialize a transaction.
          storefront_customer_email: input.email,
        } },
      });
      const session = createdSession as unknown as Record<string, unknown>;
      return { kind: "checkout", checkout: sessionCheckout(session, providerId, input.fulfillment_type, hold.expires_at) } as const;
    });
    if (result.kind === "hold-changed") {
      res.status(409).json({ message: "Checkout changed. Review your bag before continuing.", changes: result.changes });
      return;
    }
    if (result.kind === "quote-changed") {
      res.status(409).json({ code: "checkout_review_changed", message: "Review your order total again before paying." });
      return;
    }
    if (result.kind === "review") {
      res.status(200).json({ quote: result.quote });
      return;
    }
    res.status(200).json({ checkout: result.checkout });
  } catch (error) {
    const status = error instanceof MedusaError && error.type === MedusaError.Types.INVALID_DATA ? 400
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_FOUND ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.NOT_ALLOWED ? 404
      : error instanceof MedusaError && error.type === MedusaError.Types.CONFLICT ? 409
      : 503;
    res.status(status).json({ message: error instanceof Error ? error.message : "Checkout is temporarily unavailable" });
  }
}
