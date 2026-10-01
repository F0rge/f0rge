import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const authState = vi.hoisted(() => ({ getCustomerContext: vi.fn(), customerMedusaFetch: vi.fn() }));
vi.mock("@/lib/customer-auth", () => ({
  CustomerAuthError: class CustomerAuthError extends Error { constructor(public status: number) { super("account unavailable"); } },
  getCustomerContext: authState.getCustomerContext,
  customerMedusaFetch: authState.customerMedusaFetch,
}));

import { POST } from "./route";

describe("account guest-order claim BFF", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.getCustomerContext.mockResolvedValue({ id: "cus_current", token: "server-medusa-token" });
    authState.customerMedusaFetch.mockResolvedValue({ status: 200, payload: { claimed: true } });
  });

  it("takes only the route order ID and signed-in server context, never a typed email or customer ID", async () => {
    const request = new NextRequest("https://store.example/api/account/orders/order_guest_1/claim", {
      method: "POST", headers: { host: "store.example", origin: "https://store.example", "content-type": "application/json" },
      body: JSON.stringify({ email: "victim@example.com", customer_id: "cus_victim" }),
    });
    const response = await POST(request, { params: Promise.resolve({ id: "order_guest_1" }) });
    expect(response.status).toBe(200);
    expect(authState.customerMedusaFetch).toHaveBeenCalledWith(expect.objectContaining({ token: "server-medusa-token" }),
      "/store/orders/storefront-account/order_guest_1/claim", "POST", {});
    expect(await response.json()).toEqual({ claimed: true, already_owned: false });
    expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
  });

  it("rejects cross-origin claims before obtaining or forwarding customer data", async () => {
    const request = new NextRequest("https://store.example/api/account/orders/order_guest_1/claim", {
      method: "POST", headers: { host: "store.example", origin: "https://attacker.example" },
    });
    const response = await POST(request, { params: Promise.resolve({ id: "order_guest_1" }) });
    expect(response.status).toBe(403);
    expect(authState.getCustomerContext).not.toHaveBeenCalled();
    expect(authState.customerMedusaFetch).not.toHaveBeenCalled();
  });
});
