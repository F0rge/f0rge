import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import {
  classifyOpsResponse,
  buildPayload,
  retryDelaySeconds,
  retryableStorefrontOutbox,
  deliverStorefrontOrderOutbox,
  withStorefrontOrderHandoffLock,
} from "./storefront-order-handoff";

const now = new Date("2026-09-28T12:00:00.000Z");
const payload = { external_order_id: "order-test" };

function medusaMoney(numeric: number) {
  return { numeric_: numeric, raw_: { value: numeric, precision: 20 }, bignumber_: {} };
}

test("snapshots Medusa money values in minor units without relabeling non-ZAR orders", () => {
  const priorCompany = process.env.FIRSTOUT_OPS_COMPANY_ID;
  process.env.FIRSTOUT_OPS_COMPANY_ID = "company-test";
  const order = {
    id: "order-live-shape",
    created_at: "2026-09-28T12:00:00.000Z",
    email: "customer@example.test",
    customer_id: "customer-test",
    currency_code: "zar",
    total: medusaMoney(1150),
    shipping_total: medusaMoney(0),
    tax_total: medusaMoney(150),
    metadata: { storefront_checkout: { fulfillment_type: "collection" } },
    shipping_address: {
      first_name: "Checkout", last_name: "Guest", address_1: "1 Test Street", address_2: "",
      city: "Johannesburg", province: "Gauteng", postal_code: "2000", country_code: "za", phone: "+27110000000",
    },
    billing_address: { address_1: "1 Test Street", city: "Johannesburg", province: "Gauteng", postal_code: "2000", country_code: "za" },
    items: [{
      id: "item-test", title: "Test chair", quantity: 1,
      total: medusaMoney(1150), subtotal: medusaMoney(1000), tax_total: medusaMoney(150),
      variant: { sku: "SKU-TEST", metadata: { source_sku_id: "source-sku-test" } },
    }],
    shipping_methods: [],
    payment_collections: [{ payments: [{
      id: "pay-test", provider_id: "pp_storefront-test_local", amount: medusaMoney(1150),
      currency_code: "zar", captured_at: "2026-09-28T12:00:00.000Z", data: {},
    }] }],
  };

  try {
    expect(buildPayload(order)).toMatchObject({
      currency_code: "ZAR",
      totals: { subtotal_ex_minor_zar: 100000, tax_minor_zar: 15000, total_minor_zar: 115000 },
      lines: [{ ex_minor_zar: 100000, vat_minor_zar: 15000, total_minor_zar: 115000 }],
      payment: { amount_minor_zar: 115000, currency_code: "ZAR" },
    });
    expect(() => buildPayload({ ...order, currency_code: "usd" })).toThrow("invalid_currency_code");
  } finally {
    if (priorCompany === undefined) delete process.env.FIRSTOUT_OPS_COMPANY_ID;
    else process.env.FIRSTOUT_OPS_COMPANY_ID = priorCompany;
  }
});

test("uses bounded exponential backoff for durable retries", () => {
  expect(retryDelaySeconds(1)).toBe(15);
  expect(retryDelaySeconds(2)).toBe(30);
  expect(retryDelaySeconds(3)).toBe(60);
  expect(retryDelaySeconds(20)).toBe(1800);
});

test("classifies accepted, stock-conflict, idempotency-conflict, and temporary responses", () => {
  expect(classifyOpsResponse(201, { status: "imported" })).toEqual({
    status: "imported", failure_code: null, retry: false,
  });
  expect(classifyOpsResponse(202, { status: "stock_conflict" })).toEqual({
    status: "stock_conflict", failure_code: "stock_unavailable", retry: false,
  });
  expect(classifyOpsResponse(409, { detail: "customer@example.com changed the payload" })).toEqual({
    status: "failed", failure_code: "idempotency_conflict", retry: false,
  });
  expect(classifyOpsResponse(503, { detail: "internal database details" })).toEqual({
    status: "retry_wait", failure_code: "ops_unavailable", retry: true,
  });
});

test("only retries pending, due, or expired durable outboxes", () => {
  expect(retryableStorefrontOutbox({ status: "pending", payload }, now)).toBe(true);
  expect(retryableStorefrontOutbox({
    status: "retry_wait", payload, next_attempt_at: "2026-09-28T12:00:01.000Z",
  }, now)).toBe(false);
  expect(retryableStorefrontOutbox({
    status: "retry_wait", payload, next_attempt_at: "2026-09-28T11:59:59.000Z",
  }, now)).toBe(true);
  expect(retryableStorefrontOutbox({
    status: "processing", payload, lease_until: "2026-09-28T12:00:30.000Z",
  }, now)).toBe(false);
  expect(retryableStorefrontOutbox({
    status: "processing", payload, lease_until: "2026-09-28T11:59:59.000Z",
  }, now)).toBe(true);
  expect(retryableStorefrontOutbox({ status: "stock_conflict", payload }, now)).toBe(false);
  expect(retryableStorefrontOutbox({ status: "pending", payload: null }, now)).toBe(false);
});

test("serializes duplicate subscriber and scheduled-job attempts for the same order", async () => {
  const tails = new Map<string, Promise<void>>();
  const execute = async <T>(key: string, operation: () => Promise<T>): Promise<T> => {
    const prior = tails.get(key) || Promise.resolve();
    let release = () => {};
    const current = new Promise<void>((resolve) => { release = resolve; });
    const tail = prior.then(() => current);
    tails.set(key, tail);
    await prior;
    try {
      return await operation();
    } finally {
      release();
      if (tails.get(key) === tail) tails.delete(key);
    }
  };
  const locking = { execute };
  const container = {
    resolve: jest.fn((key: string) => {
      expect(key).toBe(Modules.LOCKING);
      return locking;
    }),
  } as unknown as MedusaContainer;
  let active = 0;
  let maxActive = 0;
  const attempt = () => withStorefrontOrderHandoffLock(container, "order-race", async () => {
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    active -= 1;
  });

  await Promise.all([attempt(), attempt(), attempt()]);
  expect(maxActive).toBe(1);
  expect(container.resolve).toHaveBeenCalledTimes(3);
});

test("delivery preparation shares the inventory lock across different paid orders", async () => {
  const tails = new Map<string, Promise<void>>();
  let inventoryActive = 0;
  let peakInventoryActive = 0;
  const locking = {
    execute: async <T>(key: string, operation: () => Promise<T>): Promise<T> => {
      const prior = tails.get(key) || Promise.resolve();
      let release = () => {};
      const current = new Promise<void>((resolve) => { release = resolve; });
      const tail = prior.then(() => current);
      tails.set(key, tail);
      await prior;
      if (key === "storefront:inventory") {
        inventoryActive += 1;
        peakInventoryActive = Math.max(peakInventoryActive, inventoryActive);
      }
      try {
        await new Promise((resolve) => setTimeout(resolve, 2));
        return await operation();
      } finally {
        if (key === "storefront:inventory") inventoryActive -= 1;
        release();
        if (tails.get(key) === tail) tails.delete(key);
      }
    },
  };
  const query = {
    graph: jest.fn(async ({ filters }: { filters: { id: string } }) => ({
      data: [{
        id: filters.id,
        metadata: {
          storefront_confirmation_sha256: "captured",
          storefront_handoff_outbox: { status: "imported", payload: { external_order_id: filters.id } },
        },
      }],
    })),
  };
  const container = {
    resolve: jest.fn((key: string) => key === Modules.LOCKING ? locking : key === ContainerRegistrationKeys.QUERY ? query : undefined),
  } as unknown as MedusaContainer;

  await Promise.all([
    deliverStorefrontOrderOutbox(container, "order-one"),
    deliverStorefrontOrderOutbox(container, "order-two"),
  ]);

  expect(peakInventoryActive).toBe(1);
  expect(query.graph).toHaveBeenCalledTimes(4);
});
