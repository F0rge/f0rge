import { createHmac } from "node:crypto";
import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { GET } from "./route";

const secret = "storefront-test-secret-with-more-than-32-characters";
const orderId = "order_private123";
const digest = "c".repeat(64);
const token = createHmac("sha256", secret)
  .update(`storefront-order-status:v1:${orderId}:${digest}`)
  .digest("base64url");

function fixture(suppliedToken?: string) {
  const query = { graph: jest.fn(async () => ({ data: [{
    id: orderId,
    display_id: 753,
    email: "private@example.test",
    currency_code: "zar",
    subtotal: 0,
    shipping_total: 0,
    tax_total: 0,
    total: 0,
    items: [{ id: "item-original", title: "Original item", quantity: 1, unit_price: 0, total: 0, metadata: {} }],
    shipping_methods: [],
    shipping_address: null,
    metadata: {
      storefront_confirmation_sha256: digest,
      storefront_handoff_outbox: {
        status: "imported",
        payload: {
          external_order_id: orderId,
          currency_code: "ZAR",
          totals: { subtotal_ex_minor_zar: 10000, tax_minor_zar: 1500, delivery_ex_minor_zar: 0, delivery_total_minor_zar: 0, total_minor_zar: 11500 },
          payment: { amount_minor_zar: 11500, currency_code: "ZAR", captured_at: "2026-10-01T12:00:00.000Z" },
          lines: [{ external_line_id: "item-original", total_minor_zar: 11500 }],
        },
      },
    },
  }] })) };
  const req = {
    params: { id: orderId },
    headers: suppliedToken ? { "x-storefront-order-status-token": suppliedToken } : {},
    scope: { resolve: (key: string) => key === ContainerRegistrationKeys.QUERY ? query : undefined },
  } as unknown as MedusaRequest;
  const response = {
    headers: {} as Record<string, string>,
    statusCode: 0,
    body: undefined as unknown,
    setHeader(name: string, value: string) { this.headers[name] = value; return this; },
    status(code: number) { this.statusCode = code; return this; },
    json(body: unknown) { this.body = body; return this; },
  } as unknown as MedusaResponse & { statusCode: number; body: unknown; headers: Record<string, string> };
  return { req, response, query };
}

test("requires the derived order capability even when an order ID is known", async () => {
  const priorSecret = process.env.STOREFRONT_BFF_SECRET;
  process.env.STOREFRONT_BFF_SECRET = secret;
  const { req, response } = fixture();
  try {
    await GET(req, response);
    expect(response.statusCode).toBe(404);
    expect(response.body).toEqual({ message: "Order status not found" });
  } finally {
    if (priorSecret === undefined) delete process.env.STOREFRONT_BFF_SECRET;
    else process.env.STOREFRONT_BFF_SECRET = priorSecret;
  }
});

test("returns the status snapshot only for the matching signed order capability", async () => {
  const priorSecret = process.env.STOREFRONT_BFF_SECRET;
  process.env.STOREFRONT_BFF_SECRET = secret;
  const { req, response } = fixture(token);
  try {
    await GET(req, response);
    expect(response.statusCode).toBe(200);
    expect(response.headers["Cache-Control"]).toContain("no-store");
    expect(response.headers["Referrer-Policy"]).toBe("no-referrer");
    expect(response.body).toMatchObject({
      status: "captured",
      order: {
        reference: 753,
        email: "private@example.test",
        fulfillment_status: "confirmed",
        total: 115,
        subtotal: 100,
        tax_total: 15,
        captured_amount_minor: 11500,
        captured_at: "2026-10-01T12:00:00.000Z",
        items: [{ total: 115, unit_price: 115 }],
      },
    });
  } finally {
    if (priorSecret === undefined) delete process.env.STOREFRONT_BFF_SECRET;
    else process.env.STOREFRONT_BFF_SECRET = priorSecret;
  }
});
