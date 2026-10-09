import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({
  cookies: new Map<string, string>(),
  customer: null as { id: string; email: string; first_name: string; last_name: string } | null,
}));
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: async () => ({
  get: (name: string) => state.cookies.has(name) ? { value: state.cookies.get(name) } : undefined,
}) }));
vi.mock("@/lib/customer-auth", () => ({
  getCustomerContext: async () => state.customer,
  CustomerAuthError: class CustomerAuthError extends Error { constructor(public status: number) { super("Account unavailable"); } },
}));
vi.mock("@/lib/analytics/posthog-server", () => ({ publishConfirmationOutcomes: async () => [] }));

import { cartCookie, orderAccessCookie, signedCart, signedOrderAccess, verifyCart } from "@/lib/bag-server";
import { GET, POST } from "./route";
import { GET as confirmation } from "../order/confirmation/route";
import { POST as openAccount } from "../account/session/route";

const token = "a".repeat(43);
const completedCart = {
  id: "cart_paid", completed_at: "2026-10-08T12:00:00.000Z", items: [],
  total: 100, subtotal: 100, currency_code: "zar",
  metadata: { storefront_hold: { status: "active", expires_at: "2099-01-01T00:00:00.000Z" } },
};
const newCart = { id: "cart_new", items: [], total: 0, subtotal: 0, currency_code: "zar" };

function request(path: string, body?: unknown) {
  return new NextRequest(`http://localhost:3004${path}`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function medusaFixture() {
  return vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    if (path === "/store/regions") return Response.json({ regions: [{ id: "reg_za", currency_code: "zar" }] });
    if (path === "/store/carts" && init?.method === "POST") return Response.json({ cart: newCart });
    if (path === "/store/carts/cart_paid/storefront-customer") return Response.json({ message: "Bag not found" }, { status: 404 });
    if (path === "/store/carts/cart_new/storefront-customer") return Response.json({ cart: { id: newCart.id } });
    if (path === "/store/carts/cart_paid") return Response.json({ cart: completedCart });
    if (path === "/store/carts/cart_paid/line-items") return Response.json({ message: "Cart cart_paid is already completed." }, { status: 400 });
    if (path === "/store/carts/cart_new/line-items") return Response.json({ cart: {
      ...newCart, total: 250, subtotal: 250,
      items: [{ id: "cali_new", variant_id: "variant_next", title: "Next chair", quantity: 1, unit_price: 250, total: 250 }],
    } });
    if (path === "/store/carts/cart_paid/storefront-confirmation") {
      expect(new Headers(init?.headers).get("x-storefront-confirmation-token")).toBe(token);
      return Response.json({ status: "captured", order: { reference: 123 } });
    }
    throw new Error(`Unexpected Medusa path: ${path}`);
  });
}

describe("repeat purchases", () => {
  beforeEach(() => {
    vi.stubEnv("STOREFRONT_BFF_SECRET", "a-test-secret-that-is-at-least-32-characters");
    vi.stubEnv("NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY", "pk_test");
    state.cookies.clear(); state.customer = null;
    state.cookies.set(cartCookie, signedCart(completedCart.id));
    state.cookies.set(orderAccessCookie, signedOrderAccess(completedCart.id, token));
  });

  it.each(["guest", "signed-in"])("starts a second %s purchase and retains the last paid confirmation", async (mode) => {
    if (mode === "signed-in") state.customer = { id: "cus_current", email: "customer@example.com", first_name: "A", last_name: "Customer" };
    const fetcher = medusaFixture(); vi.stubGlobal("fetch", fetcher);
    const oldAccess = state.cookies.get(orderAccessCookie);
    const emptyBag = await GET();
    expect(emptyBag.status).toBe(200);
    expect(await emptyBag.json()).toMatchObject({ id: null, items: [] });
    const added = await POST(request("/api/bag", { variant_id: "variant_next", quantity: 1 }));
    expect(added.status).toBe(200);
    expect(await added.json()).toMatchObject({ id: "cart_new", items: [{ variant_id: "variant_next" }] });
    const rotated = added.cookies.get(cartCookie);
    expect(rotated?.httpOnly).toBe(true);
    expect(verifyCart(rotated?.value)).toBe("cart_new");
    state.cookies.set(cartCookie, rotated!.value);
    expect(added.cookies.get(orderAccessCookie)).toBeUndefined();
    expect(state.cookies.get(orderAccessCookie)).toBe(oldAccess);
    const prior = await confirmation(new NextRequest("http://localhost:3004/api/order/confirmation"));
    expect(prior.status).toBe(200);
    expect(await prior.json()).toEqual({ status: "captured", order: { reference: 123 } });
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("/cart_paid/line-items"))).toBe(false);
    if (mode === "signed-in") {
      const addCall = fetcher.mock.calls.find(([url]) => String(url).endsWith("/cart_new/line-items"));
      expect(new Headers(addCall?.[1]?.headers).get("x-storefront-customer-id")).toBe("cus_current");
    }
  });

  it("retains confirmation access when account bootstrap discards a completed cart", async () => {
    state.customer = { id: "cus_current", email: "customer@example.com", first_name: "A", last_name: "Customer" };
    vi.stubGlobal("fetch", medusaFixture());
    const response = await openAccount(request("/api/account/session"));
    expect(response.status).toBe(200);
    expect(response.cookies.get(cartCookie)?.maxAge).toBe(0);
    expect(response.cookies.get(orderAccessCookie)).toBeUndefined();
    state.cookies.delete(cartCookie);
    const prior = await confirmation(new NextRequest("http://localhost:3004/api/order/confirmation"));
    expect(prior.status).toBe(200);
    expect(await prior.json()).toMatchObject({ order: { reference: 123 } });
  });

  it("does not replace an active reservation or a cart whose availability is unknown", async () => {
    const fetcher = vi.fn(async () => Response.json({ cart: { ...completedCart, completed_at: null } }));
    vi.stubGlobal("fetch", fetcher);
    const held = await POST(request("/api/bag", { variant_id: "variant_next", quantity: 1 }));
    expect(held.status).toBe(409);
    expect(fetcher).toHaveBeenCalledTimes(1);
    fetcher.mockImplementation(async () => Response.json({ message: "Unavailable" }, { status: 503 }));
    const unavailable = await POST(request("/api/bag", { variant_id: "variant_next", quantity: 1 }));
    expect(unavailable.status).toBe(503);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(unavailable.cookies.get(cartCookie)).toBeUndefined();
  });

  it("rejects tampered independent confirmation capabilities", async () => {
    state.cookies.delete(cartCookie);
    state.cookies.set(orderAccessCookie, signedOrderAccess(completedCart.id, token).replace(token, "b".repeat(43)));
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    const response = await confirmation(new NextRequest("http://localhost:3004/api/order/confirmation"));
    expect(response.status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
