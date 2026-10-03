import { opaqueAnalyticsId, type AnalyticsCustomerType } from "./attribution";
import { asMinorUnits } from "./money";
import type { AnalyticsProperties, SanitizedAnalyticsEvent } from "./events";

export type CheckoutType = "guest" | "account";
export type CheckoutStep = "contact" | "fulfillment" | "payment";
export type ShippingMethodId = "delivery" | "collection";
export type PaymentProviderId = "test_simulator" | "peach";
export type PaymentReasonFamily = "declined" | "cancelled" | "unknown";
export type FrictionSurface = "bag" | "checkout" | "payment" | "account";
export type FrictionKind = "payment_declined" | "payment_cancelled" | "payment_unknown" | "reservation_expired" | "checkout_unavailable";

export type StorefrontCommerceBrowserEvent =
  | { name: "storefront_cart_viewed"; properties: { cart_id: string; item_count: number; value_minor: number } }
  | { name: "storefront_cart_item_added"; properties: { variant_id: string; quantity: number; value_minor: number; product_id?: string; cart_id?: string } }
  | { name: "storefront_cart_item_removed"; properties: { variant_id: string; quantity: number; value_minor: number; product_id?: string; cart_id?: string } }
  | { name: "storefront_checkout_started"; properties: { cart_id: string; item_count: number; value_minor: number; checkout_type: CheckoutType } }
  | { name: "storefront_checkout_step_completed"; properties: { cart_id: string; step: CheckoutStep; checkout_type: CheckoutType } }
  | { name: "storefront_shipping_method_selected"; properties: { cart_id: string; method_id: ShippingMethodId } }
  | { name: "storefront_account_signed_in"; properties: { method: "passwordless"; anonymous_id: string } }
  | { name: "storefront_account_created"; properties: { method: "passwordless"; anonymous_id: string } }
  | { name: "storefront_study_entered"; properties: { study_id: "sola-chair-editorial" } }
  | { name: "storefront_study_progress"; properties: { study_id: "sola-chair-editorial"; milestone: 25 | 50 | 75 | 100 } }
  | { name: "storefront_study_finished"; properties: { study_id: "sola-chair-editorial" } }
  | { name: "storefront_friction_noted"; properties: { surface: FrictionSurface; kind: FrictionKind } };

export type StorefrontServerEvent =
  | { name: "storefront_order_completed"; properties: { analytics_order_id: string; value_minor: number; item_count: number; currency: "ZAR"; customer_type?: AnalyticsCustomerType } }
  | { name: "storefront_order_refunded"; properties: { analytics_order_id: string; refund_id: string; refund_minor: number; currency: "ZAR" } }
  | { name: "storefront_payment_failed"; properties: { analytics_order_id: string; provider: PaymentProviderId; reason_family: PaymentReasonFamily } };

const checkoutTypes = new Set<CheckoutType>(["guest", "account"]);
const checkoutSteps = new Set<CheckoutStep>(["contact", "fulfillment", "payment"]);
const shippingMethods = new Set<ShippingMethodId>(["delivery", "collection"]);
const providers = new Set<PaymentProviderId>(["test_simulator", "peach"]);
const reasons = new Set<PaymentReasonFamily>(["declined", "cancelled", "unknown"]);
const frictionSurfaces = new Set<FrictionSurface>(["bag", "checkout", "payment", "account"]);
const frictionKinds = new Set<FrictionKind>(["payment_declined", "payment_cancelled", "payment_unknown", "reservation_expired", "checkout_unavailable"]);
const customerTypes = new Set<AnalyticsCustomerType>(["guest", "new", "returning"]);
const STUDY_ID = "sola-chair-editorial";

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function boundedInteger(value: unknown, min: number, max: number): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max ? value : null;
}

function withSchema(properties: AnalyticsProperties, money = false): AnalyticsProperties {
  return money ? { schema_version: 1, currency: "ZAR", ...properties } : { schema_version: 1, ...properties };
}

/** Payment is a funnel step only after the order is captured, keyed by the opaque order id. */
export function confirmedPaymentStep(input: {
  status: unknown;
  analyticsOrderId: unknown;
  customerType: unknown;
}): Extract<StorefrontCommerceBrowserEvent, { name: "storefront_checkout_step_completed" }> | null {
  if (input.status !== "captured") return null;
  const cartId = opaqueAnalyticsId(input.analyticsOrderId);
  if (!cartId) return null;
  const checkoutType = input.customerType === "new" || input.customerType === "returning" ? "account" : "guest";
  return {
    name: "storefront_checkout_step_completed",
    properties: { cart_id: cartId, step: "payment", checkout_type: checkoutType },
  };
}

export function sanitizeCommerceBrowserEvent(input: unknown): SanitizedAnalyticsEvent | null {
  const event = record(input);
  const properties = record(event?.properties);
  if (!event || !properties || typeof event.name !== "string") return null;

  switch (event.name) {
    case "storefront_cart_viewed":
    case "storefront_checkout_started": {
      const cartId = opaqueAnalyticsId(properties.cart_id);
      const itemCount = boundedInteger(properties.item_count, 0, 99);
      const valueMinor = asMinorUnits(properties.value_minor);
      if (!cartId || itemCount === null || valueMinor === null) return null;
      if (event.name === "storefront_checkout_started" && !checkoutTypes.has(properties.checkout_type as CheckoutType)) return null;
      const safe: AnalyticsProperties = { cart_id: cartId, item_count: itemCount, value_minor: valueMinor };
      if (event.name === "storefront_checkout_started") safe.checkout_type = properties.checkout_type as string;
      return { name: event.name, properties: withSchema(safe, true) };
    }
    case "storefront_cart_item_added":
    case "storefront_cart_item_removed": {
      const variantId = opaqueAnalyticsId(properties.variant_id);
      const quantity = boundedInteger(properties.quantity, 1, 99);
      const valueMinor = asMinorUnits(properties.value_minor);
      if (!variantId || quantity === null || valueMinor === null) return null;
      const safe: AnalyticsProperties = { variant_id: variantId, quantity, value_minor: valueMinor };
      const productId = properties.product_id === undefined ? null : opaqueAnalyticsId(properties.product_id);
      if (properties.product_id !== undefined && !productId) return null;
      if (productId) safe.product_id = productId;
      const cartId = properties.cart_id === undefined ? null : opaqueAnalyticsId(properties.cart_id);
      if (properties.cart_id !== undefined && !cartId) return null;
      if (cartId) safe.cart_id = cartId;
      return { name: event.name, properties: withSchema(safe, true) };
    }
    case "storefront_checkout_step_completed": {
      const cartId = opaqueAnalyticsId(properties.cart_id);
      if (!cartId || !checkoutSteps.has(properties.step as CheckoutStep) || !checkoutTypes.has(properties.checkout_type as CheckoutType)) return null;
      return { name: event.name, properties: withSchema({ cart_id: cartId, step: properties.step as string, checkout_type: properties.checkout_type as string }) };
    }
    case "storefront_shipping_method_selected": {
      const cartId = opaqueAnalyticsId(properties.cart_id);
      if (!cartId || !shippingMethods.has(properties.method_id as ShippingMethodId)) return null;
      return { name: event.name, properties: withSchema({ cart_id: cartId, method_id: properties.method_id as string }) };
    }
    case "storefront_account_signed_in":
    case "storefront_account_created": {
      const anonymousId = opaqueAnalyticsId(properties.anonymous_id);
      if (properties.method !== "passwordless" || !anonymousId) return null;
      return { name: event.name, properties: withSchema({ method: "passwordless", anonymous_id: anonymousId }) };
    }
    case "storefront_study_entered":
    case "storefront_study_finished": {
      if (properties.study_id !== STUDY_ID) return null;
      return { name: event.name, properties: withSchema({ study_id: STUDY_ID }) };
    }
    case "storefront_study_progress": {
      if (properties.study_id !== STUDY_ID || ![25, 50, 75, 100].includes(properties.milestone as number)) return null;
      return { name: event.name, properties: withSchema({ study_id: STUDY_ID, milestone: properties.milestone as number }) };
    }
    case "storefront_friction_noted": {
      if (!frictionSurfaces.has(properties.surface as FrictionSurface) || !frictionKinds.has(properties.kind as FrictionKind)) return null;
      return { name: event.name, properties: withSchema({ surface: properties.surface as string, kind: properties.kind as string }) };
    }
    default:
      return null;
  }
}

export function sanitizeServerEvent(input: unknown): SanitizedAnalyticsEvent | null {
  const event = record(input);
  const properties = record(event?.properties);
  if (!event || !properties || typeof event.name !== "string") return null;

  switch (event.name) {
    case "storefront_order_completed": {
      const orderId = opaqueAnalyticsId(properties.analytics_order_id);
      const valueMinor = asMinorUnits(properties.value_minor);
      const itemCount = boundedInteger(properties.item_count, 0, 99);
      if (!orderId || valueMinor === null || itemCount === null || properties.currency !== "ZAR") return null;
      const safe: AnalyticsProperties = { analytics_order_id: orderId, value_minor: valueMinor, item_count: itemCount, currency: "ZAR" };
      if (properties.customer_type !== undefined) {
        if (!customerTypes.has(properties.customer_type as AnalyticsCustomerType)) return null;
        safe.customer_type = properties.customer_type as string;
      }
      return { name: event.name, properties: withSchema(safe, true) };
    }
    case "storefront_order_refunded": {
      const orderId = opaqueAnalyticsId(properties.analytics_order_id);
      const refundId = opaqueAnalyticsId(properties.refund_id);
      const refundMinor = asMinorUnits(properties.refund_minor);
      if (!orderId || !refundId || refundMinor === null || refundMinor <= 0 || properties.currency !== "ZAR") return null;
      return { name: event.name, properties: withSchema({ analytics_order_id: orderId, refund_id: refundId, refund_minor: refundMinor, currency: "ZAR" }, true) };
    }
    case "storefront_payment_failed": {
      const orderId = opaqueAnalyticsId(properties.analytics_order_id);
      if (!orderId || !providers.has(properties.provider as PaymentProviderId) || !reasons.has(properties.reason_family as PaymentReasonFamily)) return null;
      return { name: event.name, properties: withSchema({ analytics_order_id: orderId, provider: properties.provider as string, reason_family: properties.reason_family as string }) };
    }
    default:
      return null;
  }
}

export function commerceInsertId(name: SanitizedAnalyticsEvent["name"], parts: string[]): string {
  const body = [name, ...parts].map((part) => part.replace(/[^A-Za-z0-9_-]/g, "")).join(":");
  return body.slice(0, 200);
}
