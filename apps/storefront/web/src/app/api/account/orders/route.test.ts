import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({ getCustomerContext: vi.fn(), customerMedusaFetch: vi.fn() }));
vi.mock("@/lib/customer-auth", () => ({
  CustomerAuthError: class CustomerAuthError extends Error { constructor(public status: number) { super("account unavailable"); } },
  getCustomerContext: authState.getCustomerContext,
  customerMedusaFetch: authState.customerMedusaFetch,
}));

import { GET } from "./route";

describe("account order history BFF", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.getCustomerContext.mockResolvedValue({ id: "cus_current", token: "server-medusa-token", email: "current@example.com" });
  });

  it("uses the signed-in native order list and allowlists fields before returning it", async () => {
    authState.customerMedusaFetch
      .mockResolvedValueOnce({ status: 200, payload: {
        count: 1,
        orders: [{ id: "order_current", display_id: 17, created_at: "2026-10-01T00:00:00.000Z", currency_code: "zar", status: "completed", total: 12.5, metadata: { storefront_handoff_outbox: ["private"] }, email: "private@example.com" }],
      } })
      .mockResolvedValueOnce({ status: 200, payload: { orders: [] } });
    const response = await GET(new Request("https://store.example/api/account/orders?customer_id=cus_other"));
    const body = await response.json() as { orders: Record<string, unknown>[] };
    expect(authState.customerMedusaFetch).toHaveBeenNthCalledWith(1, expect.objectContaining({ token: "server-medusa-token" }),
      "/store/orders?limit=50&offset=0&fields=id,display_id,created_at,currency_code,status,total");
    expect(authState.customerMedusaFetch.mock.calls[0][1]).not.toContain("cus_other");
    expect(body.orders).toEqual([expect.objectContaining({ id: "order_current", reference: 17, total: 12.5 })]);
    expect(body.orders[0]).not.toHaveProperty("email");
    expect(body.orders[0]).not.toHaveProperty("metadata");
    expect(response.headers.get("cache-control")).toBe("private, no-store, max-age=0");
    expect(response.headers.get("x-robots-tag")).toContain("noindex");
  });

  it("paginates owned history and only queries guest claims on the first page", async () => {
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { count: 103, orders: Array.from({ length: 50 }, (_, index) => ({ id: `order_${index}` })) } });
    const response = await GET(new Request("https://store.example/api/account/orders?offset=50"));
    const body = await response.json() as { offset: number; hasMore: boolean; claimable: unknown[] };
    expect(authState.customerMedusaFetch).toHaveBeenCalledTimes(1);
    expect(authState.customerMedusaFetch.mock.calls[0][1]).toContain("offset=50");
    expect(body).toMatchObject({ offset: 50, hasMore: true, claimable: [] });
  });

  it("does not call Medusa if there is no signed-in customer", async () => {
    authState.getCustomerContext.mockResolvedValue(null);
    const response = await GET(new Request("https://store.example/api/account/orders"));
    expect(response.status).toBe(401);
    expect(authState.customerMedusaFetch).not.toHaveBeenCalled();
  });
});
