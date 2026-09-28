import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const cartCookie = "collector_cart";
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

export type BagItem = { id: string; variant_id: string; title: string; thumbnail?: string | null; quantity: number; unit_price: number; total: number };
export type Bag = { id: string | null; items: BagItem[]; subtotal: number; total: number; currency_code: string; hold?: { expires_at: string; status: string; changes?: string[] } | null };
type MedusaCart = Omit<Bag, "id"> & { id: string; metadata?: { storefront_hold?: Bag["hold"] } };

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

export function publicBag(cart?: MedusaCart | null): Bag {
  if (!cart) return { id: null, items: [], subtotal: 0, total: 0, currency_code: "zar" };
  return {
    id: cart.id,
    items: (cart.items || []).map(({ id, variant_id, title, thumbnail, quantity, unit_price, total }) => ({
      id, variant_id, title, thumbnail, quantity, unit_price, total,
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
