import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const cookies = vi.hoisted(() => new Map<string, string>());
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: async () => ({
  get: (name: string) => cookies.has(name) ? { value: cookies.get(name) } : undefined,
}) }));
vi.mock("@/lib/customer-auth", () => ({
  getCustomerContext: async () => null,
  CustomerAuthError: class CustomerAuthError extends Error {},
}));

import { cartCookie, orderAccessCookie, signedCart, signedOrderAccess } from "@/lib/bag-server";
import { POST } from "./route";

beforeEach(() => {
  vi.stubEnv("STOREFRONT_BFF_SECRET", "a-test-secret-that-is-at-least-32-characters");
  vi.stubEnv("NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY", "pk_test");
  cookies.set(cartCookie, signedCart("cart_checkout"));
});

afterEach(() => {
  cookies.clear();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function request(body: Record<string, unknown>) {
  return new NextRequest("http://localhost:3004/api/checkout/prepare", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
}

it("passes the commerce payment_unavailable code through to the checkout page", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(
    { code: "payment_unavailable", message: "Checkout is not available here" }, { status: 404 },
  )));
  const response = await POST(request({ step: "review", fulfillment_type: "collection" }));
  expect(response.status).toBe(404);
  expect(await response.json()).toMatchObject({ code: "payment_unavailable" });
  expect(response.cookies.has(orderAccessCookie)).toBe(false);
});

it("returns the review quote without forwarding or issuing a private order token", async () => {
  const quote = { amount: 1800, currency_code: "zar", delivery_amount: 1100, review_token: "review" };
  const fetchCommerce = vi.fn(async (_: unknown, options?: RequestInit) => {
    expect(JSON.parse(String(options?.body))).toEqual({ step: "review", fulfillment_type: "delivery" });
    return Response.json({ quote });
  });
  vi.stubGlobal("fetch", fetchCommerce);
  const response = await POST(request({ step: "review", fulfillment_type: "delivery", confirmation_token: "client-value" }));
  expect(await response.json()).toEqual({ quote });
  expect(response.headers.get("Cache-Control")).toContain("no-store");
  expect(response.cookies.has(orderAccessCookie)).toBe(false);
  expect(fetchCommerce).toHaveBeenCalledOnce();
});

it("forwards the accepted review token and sets the private capability for the payment attempt", async () => {
  const fetchCommerce = vi.fn(async (_: unknown, options?: RequestInit) => {
    expect(JSON.parse(String(options?.body))).toMatchObject({
      step: "payment", review_token: "review", confirmation_token: expect.stringMatching(/^[A-Za-z0-9_-]{40,100}$/),
    });
    return Response.json({ checkout: { session_id: "session" } });
  });
  vi.stubGlobal("fetch", fetchCommerce);
  const response = await POST(request({ step: "payment", review_token: "review" }));
  expect(await response.json()).toEqual({ checkout: { session_id: "session" } });
  expect(response.cookies.get(orderAccessCookie)?.httpOnly).toBe(true);
  expect(fetchCommerce).toHaveBeenCalledOnce();
});

it("forwards an existing private capability on review without renewing the cookie", async () => {
  const capability = "a".repeat(43);
  cookies.set(orderAccessCookie, signedOrderAccess("cart_checkout", capability));
  const fetchCommerce = vi.fn(async (_: unknown, options?: RequestInit) => {
    expect(JSON.parse(String(options?.body))).toMatchObject({ step: "review", confirmation_token: capability });
    return Response.json({ quote: { amount: 1800 } });
  });
  vi.stubGlobal("fetch", fetchCommerce);
  const response = await POST(request({ step: "review", confirmation_token: "client-value" }));
  expect(await response.json()).toEqual({ quote: { amount: 1800 } });
  expect(response.cookies.has(orderAccessCookie)).toBe(false);
  expect(fetchCommerce).toHaveBeenCalledOnce();
});
