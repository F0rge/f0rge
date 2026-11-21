import { expect, it, vi } from "vitest";
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

import { cartCookie, signedCart } from "@/lib/bag-server";
import { POST } from "./route";

it("passes the commerce payment_unavailable code through to the checkout page", async () => {
  vi.stubEnv("STOREFRONT_BFF_SECRET", "a-test-secret-that-is-at-least-32-characters");
  vi.stubEnv("NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY", "pk_test");
  cookies.set(cartCookie, signedCart("cart_checkout"));
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(
    { code: "payment_unavailable", message: "Checkout is not available here" }, { status: 404 },
  )));
  const response = await POST(new NextRequest("http://localhost:3004/api/checkout/prepare", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ fulfillment_type: "collection" }),
  }));
  expect(response.status).toBe(404);
  expect(await response.json()).toMatchObject({ code: "payment_unavailable" });
});
