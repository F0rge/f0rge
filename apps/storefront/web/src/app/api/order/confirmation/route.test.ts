import { createHmac } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({ cookies: new Map<string, string>() }));
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) => (state.cookies.has(name) ? { value: state.cookies.get(name) } : undefined),
  }),
}));
vi.mock("@/lib/customer-auth", () => ({
  getCustomerContext: async () => null,
  CustomerAuthError: class CustomerAuthError extends Error {
    constructor(public status: number) {
      super("Account unavailable");
    }
  },
}));
vi.mock("@/lib/analytics/posthog-server", () => ({ publishConfirmationOutcomes: async () => [] }));

import { emailOrderAccessCookie, orderAccessCookie, signedEmailOrderAccess, signedOrderAccess } from "@/lib/bag-server";
import { GET } from "./route";

const secret = "a-test-secret-that-is-at-least-32-characters";
const paidToken = "p".repeat(43);
const pendingToken = "n".repeat(43);
const paidOrder = { status: "captured", order: { id: "order_paid", reference: 41 } };
const pendingCheckout = { status: "pending", payment: { status: "awaiting" } };

function legacyEmailCookie(orderId: string, token: string): string {
  const signature = createHmac("sha256", secret)
    .update(`email-order-cookie:v1:${orderId}:${token}`)
    .digest("base64url");
  return `e1.${orderId}.${token}.${signature}`;
}

function confirmationRequest(): NextRequest {
  return new NextRequest("http://localhost:3004/api/order/confirmation");
}

describe("order confirmation cookie precedence", () => {
  beforeEach(() => {
    vi.stubEnv("STOREFRONT_BFF_SECRET", secret);
    vi.stubEnv("NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY", "pk_test");
    state.cookies.clear();
    vi.stubGlobal("fetch", vi.fn(async (input: string | URL | Request) => {
      const path = new URL(String(input)).pathname;
      if (path === "/store/orders/order_paid/storefront-status") return Response.json(paidOrder);
      if (path === "/store/carts/cart_pending/storefront-confirmation") return Response.json(pendingCheckout);
      throw new Error(`Unexpected Medusa path: ${path}`);
    }));
  });

  it("does not let an older order-email cookie replace the checkout in progress", async () => {
    state.cookies.set(emailOrderAccessCookie, legacyEmailCookie("order_paid", paidToken));
    state.cookies.set(orderAccessCookie, signedOrderAccess("cart_pending", pendingToken, 2_000));

    const response = await GET(confirmationRequest());

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(pendingCheckout);
  });

  it("keeps a newer email confirmation ahead of an older checkout", async () => {
    state.cookies.set(orderAccessCookie, signedOrderAccess("cart_pending", pendingToken, 2_000));
    state.cookies.set(emailOrderAccessCookie, signedEmailOrderAccess("order_paid", paidToken, 3_000));

    const response = await GET(confirmationRequest());

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(paidOrder);
  });
});
