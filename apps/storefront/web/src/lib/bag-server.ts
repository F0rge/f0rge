import "server-only";

import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const cartCookie = "collector_cart";
export const orderAccessCookie = "collector_order_access";
export const emailOrderAccessCookie = "collector_email_order_access";
const baseUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000";

function secret(): string {
  const value = process.env.STOREFRONT_BFF_SECRET;
  if (!value || value.length < 32) throw new Error("STOREFRONT_BFF_SECRET must contain at least 32 characters");
  return value;
}

function signature(id: string): string {
  return createHmac("sha256", secret()).update(`v1:${id}`).digest("base64url");
}

export function signedCart(id: string): string {
  return `v1.${id}.${signature(id)}`;
}

export function verifyCart(value?: string): string | null {
  const match = /^v1\.(cart_[A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/.exec(value || "");
  if (!match) return null;
  const expected = Buffer.from(signature(match[1]));
  const actual = Buffer.from(match[2]);
  return expected.length === actual.length && timingSafeEqual(expected, actual) ? match[1] : null;
}

export async function currentCartId(): Promise<string | null> {
  return verifyCart((await cookies()).get(cartCookie)?.value);
}

function orderAccessSignature(cartId: string, token: string): string {
  return createHmac("sha256", secret()).update(`order-confirmation:v1:${cartId}:${token}`).digest("base64url");
}

function emailOrderAccessSignature(orderId: string, token: string): string {
  return createHmac("sha256", secret()).update(`email-order-cookie:v1:${orderId}:${token}`).digest("base64url");
}

export function newOrderAccessToken(): string { return randomBytes(32).toString("base64url"); }

export function signedOrderAccess(cartId: string, token: string): string {
  return `v1.${cartId}.${token}.${orderAccessSignature(cartId, token)}`;
}

export function verifyOrderAccess(value: string | undefined, cartId: string): string | null {
  const match = /^v1\.(cart_[A-Za-z0-9_-]+)\.([A-Za-z0-9_-]{40,100})\.([A-Za-z0-9_-]+)$/.exec(value || "");
  if (!match || match[1] !== cartId) return null;
  const expected = Buffer.from(orderAccessSignature(cartId, match[2]));
  const actual = Buffer.from(match[3]);
  return expected.length === actual.length && timingSafeEqual(expected, actual) ? match[2] : null;
}

export async function currentOrderAccessToken(cartId: string): Promise<string | null> {
  return verifyOrderAccess((await cookies()).get(orderAccessCookie)?.value, cartId);
}

export function signedEmailOrderAccess(orderId: string, token: string): string {
  return `e1.${orderId}.${token}.${emailOrderAccessSignature(orderId, token)}`;
}

export async function currentEmailOrderAccess(): Promise<{ orderId: string; token: string } | null> {
  const value = (await cookies()).get(emailOrderAccessCookie)?.value || "";
  const match = /^e1\.(order_[A-Za-z0-9_-]+)\.([A-Za-z0-9_-]{43})\.([A-Za-z0-9_-]{43})$/.exec(value);
  if (!match) return null;
  const expected = Buffer.from(emailOrderAccessSignature(match[1], match[2]));
  const actual = Buffer.from(match[3]);
  return expected.length === actual.length && timingSafeEqual(expected, actual)
    ? { orderId: match[1], token: match[2] }
    : null;
}

export type BagFulfillmentPromise = {
  kind: "stocked" | "made_to_order";
  offer_id?: string;
  min_lead_time_days?: number;
  max_lead_time_days?: number;
  estimated_from: string;
  estimated_by: string;
  expires_at?: string;
};
export type BagFulfillmentSummary = {
  version: 1;
  kind: "stocked" | "made_to_order" | "mixed";
  accepted_at: string;
  estimated_from: string;
  estimated_by: string;
};
export type BagItem = { id: string; variant_id: string; title: string; thumbnail?: string | null; quantity: number; unit_price: number; total: number; fulfillment_promise?: BagFulfillmentPromise | null };
export type Bag = { id: string | null; items: BagItem[]; subtotal: number; total: number; currency_code: string; hold?: { expires_at: string; status: string; changes?: string[]; fulfillment_promise?: BagFulfillmentSummary } | null };
type MedusaCart = Omit<Bag, "id" | "items"> & {
  id: string;
  items?: (Omit<BagItem, "fulfillment_promise"> & { metadata?: { fulfillment_promise?: BagFulfillmentPromise } | null })[] | null;
  metadata?: { storefront_hold?: Bag["hold"] };
};

export class BagError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function medusaResponse<T>(path: string, method = "GET", body?: unknown): Promise<{ status: number; payload: T & { message?: string } }> {
  const key = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;
  if (!key) throw new Error("Medusa publishable key is missing");
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: {
      "x-publishable-api-key": key,
      "x-storefront-bff-secret": secret(),
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as T & { message?: string };
  return { status: response.status, payload };
}

export async function medusaRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const { status, payload } = await medusaResponse<T>(path, method, body);
  if (status < 200 || status >= 300) throw new BagError(status, payload.message || "The bag could not be updated. Please try again.");
  return payload;
}

export async function orderConfirmationResponse(cartId: string, token: string): Promise<{ status: number; payload: Record<string, unknown> }> {
  const response = await fetch(`${baseUrl}/store/carts/${encodeURIComponent(cartId)}/storefront-confirmation`, {
    headers: {
      "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
      "x-storefront-bff-secret": secret(),
      "x-storefront-confirmation-token": token,
    },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  return { status: response.status, payload };
}

export async function storefrontOrderStatusResponse(orderId: string, token: string): Promise<{ status: number; payload: Record<string, unknown> }> {
  const response = await fetch(`${baseUrl}/store/orders/${encodeURIComponent(orderId)}/storefront-status`, {
    headers: {
      "x-publishable-api-key": process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY || "",
      "x-storefront-bff-secret": secret(),
      "x-storefront-order-status-token": token,
    },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  return { status: response.status, payload };
}

export function publicBag(cart?: MedusaCart | null): Bag {
  if (!cart) return { id: null, items: [], subtotal: 0, total: 0, currency_code: "zar" };
  return {
    id: cart.id,
    items: (cart.items || []).map(({ id, variant_id, title, thumbnail, quantity, unit_price, total, metadata }) => ({
      id, variant_id, title, thumbnail, quantity, unit_price, total: total ?? unit_price * quantity,
      fulfillment_promise: metadata?.fulfillment_promise || null,
    })),
    subtotal: cart.subtotal || 0, total: cart.total || 0, currency_code: cart.currency_code || "zar",
    hold: cart.metadata?.storefront_hold || null,
  };
}

export async function getCart(id: string): Promise<Bag> {
  const { cart } = await medusaRequest<{ cart: MedusaCart }>(`/store/carts/${encodeURIComponent(id)}`);
  return publicBag(cart);
}

export async function createCart(): Promise<Bag> {
  const { regions } = await medusaRequest<{ regions: { id: string; currency_code: string }[] }>("/store/regions");
  const region = regions.find((item) => item.currency_code === "zar");
  if (!region) throw new BagError(503, "The South Africa region is unavailable");
  const { cart } = await medusaRequest<{ cart: MedusaCart }>("/store/carts", "POST", { region_id: region.id });
  return publicBag(cart);
}
