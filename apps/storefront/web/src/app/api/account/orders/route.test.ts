import { beforeEach, describe, expect, it, vi } from "vitest";

const authState = vi.hoisted(() => ({ getCustomerContext: vi.fn(), customerMedusaFetch: vi.fn() }));
vi.mock("@/lib/customer-auth", () => ({
  CustomerAuthError: class CustomerAuthError extends Error { constructor(public status: number) { super("account unavailable"); } },
  getCustomerContext: authState.getCustomerContext,
  customerMedusaFetch: authState.customerMedusaFetch,
}));

import { GET } from "./route";
import { GET as getOrder } from "./[id]/route";
import AccountOrderPage from "@/app/account/orders/[id]/page";
import { renderToStaticMarkup } from "react-dom/server";
import { orderMoney } from "@/lib/order-money";

describe("account order history BFF", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.getCustomerContext.mockResolvedValue({ id: "cus_current", token: "server-medusa-token", email: "current@example.com" });
  });

  it("uses the signed-in native order list and allowlists fields before returning it", async () => {
    authState.customerMedusaFetch
      .mockResolvedValueOnce({ status: 200, payload: {
        count: 1,
        orders: [{ id: "order_current", display_id: 17, created_at: "2026-10-01T00:00:00.000Z", currency_code: "zar", status: "completed", total: 12.5, metadata: { storefront_handoff_outbox: ["private"], storefront_fulfillment_status: { fulfillment_type: "collection", status: "ready_for_collection" } }, email: "private@example.com" }],
      } })
      .mockResolvedValueOnce({ status: 200, payload: { orders: [] } });
    const response = await GET(new Request("https://store.example/api/account/orders?customer_id=cus_other"));
    const body = await response.json() as { orders: Record<string, unknown>[] };
    expect(authState.customerMedusaFetch).toHaveBeenNthCalledWith(1, expect.objectContaining({ token: "server-medusa-token" }),
      "/store/orders?limit=50&offset=0&fields=id,display_id,created_at,currency_code,status,total,metadata");
    expect(authState.customerMedusaFetch.mock.calls[0][1]).not.toContain("cus_other");
    expect(body.orders).toEqual([expect.objectContaining({
      id: "order_current", reference: 17, total: 12.5,
      fulfillment_type: "collection", fulfillment_status: "ready_for_collection",
    })]);
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

  it("keeps the captured purchase total after refund credits without exposing the financial snapshot", async () => {
    const order = {
      id: "order_refunded", display_id: 18, currency_code: "zar", total: 0,
      metadata: { storefront_refunds: [
        { provider_refund_id: "private-refund", amount_minor: 40000, currency_code: "ZAR", status: "succeeded" },
        { provider_refund_id: "private-pending", amount_minor: 75000, currency_code: "ZAR", status: "pending" },
      ], storefront_handoff_outbox: { payload: {
        external_order_id: "order_refunded", currency_code: "ZAR",
        totals: { total_minor_zar: 115000 },
        payment: { amount_minor_zar: 115000, currency_code: "ZAR", reference: "private-capture" },
        lines: [{ external_line_id: "item_original", total_minor_zar: 115000 }],
      } } },
      items: [{ id: "item_original", title: "Chair", quantity: 1, unit_price: 1150, total: 0 }],
    };
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { orders: [order] } })
      .mockResolvedValueOnce({ status: 200, payload: { orders: [] } });
    const history = await GET(new Request("https://store.example/api/account/orders"));
    expect((await history.json()).orders[0]).toMatchObject({ total: 1150 });
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { order } });
    const detail = await getOrder(new Request("https://store.example/api/account/orders/order_refunded"), {
      params: Promise.resolve({ id: "order_refunded" }),
    });
    const body = await detail.json();
    expect(body.order).toMatchObject({ total: 1150, items: [{ total: 1150 }] });
    expect(body.order.refund_status).toMatchObject({ refunded_amount_minor: 40000,
      items: [{ amount_minor: 40000, status: "succeeded" }, { amount_minor: 75000, status: "pending" }],
    });
    expect(JSON.stringify(body)).not.toContain("private-capture");
    expect(JSON.stringify(body)).not.toContain("private-refund");
    expect(body.order).not.toHaveProperty("metadata");
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { order } });
    const page = await AccountOrderPage({ params: Promise.resolve({ id: "order_refunded" }) });
    const html = renderToStaticMarkup(page);
    expect(html).toContain("Total paid");
    expect(html).toContain(orderMoney(1150, "ZAR"));
    expect(html).toContain("Pending confirmation");
    expect(html).toContain("Refunded");
    expect(html).toContain("Order confirmed");
    expect(html).toContain("Delivery");
    expect(html).not.toContain("private-refund");
  });

  it("shows collection readiness instead of the Medusa payment status", async () => {
    const order = {
      id: "order_collection", display_id: 19, currency_code: "zar", status: "completed", total: 1150,
      metadata: {
        storefront_checkout: { fulfillment_type: "collection" },
        storefront_fulfillment_status: { fulfillment_type: "collection", status: "ready_for_collection" },
      },
      items: [{ id: "item_original", title: "Chair", quantity: 1, unit_price: 1150, total: 1150 }],
    };
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { orders: [order] } })
      .mockResolvedValueOnce({ status: 200, payload: { orders: [] } });
    const history = await GET(new Request("https://store.example/api/account/orders"));
    expect((await history.json()).orders[0]).toMatchObject({
      fulfillment_type: "collection", fulfillment_status: "ready_for_collection",
    });
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { order } });
    const detail = await getOrder(new Request("https://store.example/api/account/orders/order_collection"), {
      params: Promise.resolve({ id: "order_collection" }),
    });
    expect((await detail.json()).order).toMatchObject({
      fulfillment_type: "collection", fulfillment_status: "ready_for_collection",
    });
    authState.customerMedusaFetch.mockResolvedValueOnce({ status: 200, payload: { order } });
    const html = renderToStaticMarkup(await AccountOrderPage({ params: Promise.resolve({ id: "order_collection" }) }));
    expect(html).toContain("Ready for collection");
    expect(html).toContain("Showroom collection");
    expect(html).not.toContain("Order status: completed");
  });

  it("does not call Medusa if there is no signed-in customer", async () => {
    authState.getCustomerContext.mockResolvedValue(null);
    const response = await GET(new Request("https://store.example/api/account/orders"));
    expect(response.status).toBe(401);
    expect(authState.customerMedusaFetch).not.toHaveBeenCalled();
  });
});
