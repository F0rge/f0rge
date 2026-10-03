import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import {
  applyStorefrontFulfillmentEvent,
  mergeFulfillmentEvent,
  releaseCancellationCommitmentsFromMetadata,
  syncStorefrontFulfillmentEvents,
  type StorefrontFulfillmentEvent,
} from "./storefront-fulfillment-events";
import { retryStorefrontOrderNotifications } from "./storefront-notifications";
import { availableCapacity, mergeCapacityState, reserveCapacity, consumeCapacity } from "./made-to-order-capacity";

const orderPromise = {
  version: 1,
  kind: "stocked",
  accepted_at: "2026-09-29T10:00:00.000Z",
  estimated_from: "2026-09-29",
  estimated_by: "2026-09-29",
};

function event(overrides: Partial<StorefrontFulfillmentEvent> = {}): StorefrontFulfillmentEvent {
  return {
    event_id: "4a75a5dd-bbd7-4520-9d87-75ef30a319c8",
    company_id: "company-test",
    external_order_id: "order_test123",
    revision: 1,
    fulfillment_type: "collection",
    status: "ready_for_collection",
    fulfillment_promise: orderPromise,
    occurred_at: "2026-09-29T10:01:00.000Z",
    ...overrides,
  };
}

function lockedContainer(resolve: (key: string) => unknown): MedusaContainer {
  const locking = { execute: async <T>(_key: string, fn: () => Promise<T>) => fn() };
  return {
    resolve: jest.fn((key: string) => key === Modules.LOCKING ? locking : resolve(key)),
  } as unknown as MedusaContainer;
}

test("merges duplicate and out-of-order fulfillment events without regression", () => {
  const first = event({ revision: 2, status: "collected" });
  const applied = mergeFulfillmentEvent(null, [], first, orderPromise);
  expect(applied.changed).toBe(true);
  expect(applied.state.status).toBe("collected");

  const replay = mergeFulfillmentEvent(applied.state, applied.processed, first, orderPromise);
  expect(replay.duplicate).toBe(true);
  expect(replay.changed).toBe(false);

  const stale = mergeFulfillmentEvent(applied.state, applied.processed, event({
    event_id: "d39e4149-4bbb-439b-9dd0-4b2e2d7f5a8a",
    revision: 1,
    status: "ready_for_collection",
  }), orderPromise);
  expect(stale.changed).toBe(false);
  expect(stale.state).toEqual(applied.state);
});

test("accepts the same immutable promise with Firstout's UTC offset formatting", () => {
  const offsetPromise = { ...orderPromise, accepted_at: "2026-09-29T10:00:00+00:00" };
  expect(mergeFulfillmentEvent(null, [], event({ fulfillment_promise: offsetPromise }), orderPromise).changed).toBe(true);
  expect(() => mergeFulfillmentEvent(null, [], event({
    fulfillment_promise: { ...offsetPromise, accepted_at: "2026-09-30T10:00:00+00:00" },
  }), orderPromise)).toThrow("fulfillment_promise_mismatch");
});

test("applies an authenticated fulfillment event and queues exactly one status notice", async () => {
  const priorCompany = process.env.FIRSTOUT_OPS_COMPANY_ID;
  process.env.FIRSTOUT_OPS_COMPANY_ID = "company-test";
  const order: Record<string, any> = {
    id: "order_test123",
    display_id: 753,
    email: "customer@example.test",
    metadata: {
      storefront_confirmation_sha256: "a".repeat(64),
      storefront_fulfillment_promise: orderPromise,
    },
  };
  const query = { graph: jest.fn(async () => ({ data: [order] })) };
  const orderModule = { updateOrders: jest.fn(async ([updated]: { id: string; metadata: Record<string, unknown> }[]) => {
    order.metadata = updated.metadata;
  }) };
  const container = lockedContainer((key) => key === ContainerRegistrationKeys.QUERY ? query : key === Modules.ORDER ? orderModule : undefined);

  try {
    expect(await applyStorefrontFulfillmentEvent(container, event())).toBe("applied");
    expect(order.metadata.storefront_fulfillment_status).toMatchObject({
      status: "ready_for_collection",
      revision: 1,
    });
    expect(order.metadata.storefront_notification_outbox).toHaveLength(1);
    expect(order.metadata.storefront_notification_outbox[0]).toMatchObject({
      id: "fulfillment:4a75a5dd-bbd7-4520-9d87-75ef30a319c8",
      recipient: "customer@example.test",
      data: { fulfillment: { status: "ready_for_collection" } },
    });
    expect(await applyStorefrontFulfillmentEvent(container, event())).toBe("duplicate");
    expect(orderModule.updateOrders).toHaveBeenCalledTimes(1);
  } finally {
    if (priorCompany === undefined) delete process.env.FIRSTOUT_OPS_COMPANY_ID;
    else process.env.FIRSTOUT_OPS_COMPANY_ID = priorCompany;
  }
});

test("cancellation release plan preserves unrelated paid and made-to-order commitments", () => {
  const offer = {
    id: "bcd2f5d4-237b-43fb-a152-bef10a6a3eaa",
    capacity: 2,
    min_lead_time_days: 28,
    max_lead_time_days: 42,
    expires_at: "2026-10-15T12:00:00.000Z",
  };
  const acceptedAt = new Date("2026-09-28T12:00:00.000Z");
  const initialCapacity = reserveCapacity(
    mergeCapacityState(null, offer, "2026-09-28T11:00:00.000000Z"),
    offer.id,
    "cart-test",
    "cart-mto-line",
    1,
    "2026-09-28T12:20:00.000Z",
    acceptedAt,
  );
  const committedCapacity = consumeCapacity(
    initialCapacity,
    offer.id,
    "cart-test",
    "cart-mto-line",
    "storefront:order_test123:item-mto",
    1,
    Date.parse("2026-09-28T12:01:00.000Z"),
  );
  const unrelatedCapacityHold = reserveCapacity(
    committedCapacity,
    offer.id,
    "other-cart",
    "other-mto-line",
    1,
    "2026-09-28T12:20:00.000Z",
    acceptedAt,
  );
  const withUnrelatedCapacity = consumeCapacity(
    unrelatedCapacityHold,
    offer.id,
    "other-cart",
    "other-mto-line",
    "storefront:other-order:item-mto",
    1,
    Date.parse("2026-09-28T12:01:00.000Z"),
  );
  const variant: Record<string, any> = {
    source_sku_id: "3a02d72f-25ef-44c8-b7e0-2b4680f5145e",
    source_observed_at: "2026-09-28T12:00:00.000Z",
    storefront_made_to_order_capacity: withUnrelatedCapacity,
    pending_paid_commitments: [
      { commitment_id: "storefront:order_test123:item-mto", source_sku_id: "3a02d72f-25ef-44c8-b7e0-2b4680f5145e", quantity: 1 },
      { commitment_id: "storefront:order_test123:item-stock", source_sku_id: "3a02d72f-25ef-44c8-b7e0-2b4680f5145e", quantity: 2 },
      { commitment_id: "storefront:other-order:item-stock", source_sku_id: "3a02d72f-25ef-44c8-b7e0-2b4680f5145e", quantity: 3 },
    ],
    storefront_cancellation_releases: [{ event_id: "older-event", commitment_id: "prior-order", pending_paid_quantity: 1 }],
  };
  const cancel = event({ status: "cancelled", event_id: "e480335a-7c2e-4d15-9a84-3754f7566ec6", revision: 2 });

  expect(availableCapacity(withUnrelatedCapacity.allocations[offer.id], acceptedAt.getTime())).toBe(0);
  const first = releaseCancellationCommitmentsFromMetadata(variant, [
    { commitmentId: "storefront:order_test123:item-mto", offerId: offer.id },
    { commitmentId: "storefront:order_test123:item-stock" },
  ], cancel.event_id);
  expect(first.changed).toBe(true);
  expect(first.metadata.pending_paid_commitments).toEqual([
    { commitment_id: "storefront:other-order:item-stock", source_sku_id: "3a02d72f-25ef-44c8-b7e0-2b4680f5145e", quantity: 3 },
  ]);
  expect(availableCapacity(
    first.metadata.storefront_made_to_order_capacity.allocations[offer.id], acceptedAt.getTime(),
  )).toBe(1);
  expect(first.metadata.storefront_made_to_order_capacity.allocations[offer.id].committed).toEqual({
    "storefront:other-order:item-mto": 1,
  });
  expect(first.metadata.storefront_cancellation_releases).toEqual(expect.arrayContaining([
    expect.objectContaining({ event_id: "older-event", commitment_id: "prior-order" }),
    expect.objectContaining({ event_id: cancel.event_id, commitment_id: "storefront:order_test123:item-mto", pending_paid_quantity: 1, made_to_order_quantity: 1 }),
    expect.objectContaining({ event_id: cancel.event_id, commitment_id: "storefront:order_test123:item-stock", pending_paid_quantity: 2, made_to_order_quantity: 0 }),
  ]));
  expect(first.metadata.storefront_cancellation_releases).not.toContainEqual(
    expect.objectContaining({ event_id: cancel.event_id, commitment_id: "storefront:other-order:item-stock" }),
  );

  const replay = releaseCancellationCommitmentsFromMetadata(first.metadata, [
    { commitmentId: "storefront:order_test123:item-mto", offerId: offer.id },
    { commitmentId: "storefront:order_test123:item-stock" },
  ], cancel.event_id);
  expect(replay.changed).toBe(false);
  expect(replay.metadata).toBe(first.metadata);
});

test("acknowledges a status message only after its durable order write succeeds", async () => {
  const previous = {
    url: process.env.FIRSTOUT_OPS_URL,
    token: process.env.FIRSTOUT_OPS_TOKEN,
    company: process.env.FIRSTOUT_OPS_COMPANY_ID,
  };
  process.env.FIRSTOUT_OPS_URL = "http://firstout.test/api/v1/ops-commerce/v1";
  process.env.FIRSTOUT_OPS_TOKEN = "test-service-token";
  process.env.FIRSTOUT_OPS_COMPANY_ID = "company-test";
  const order: Record<string, any> = {
    id: "order_test123",
    display_id: 753,
    email: "customer@example.test",
    metadata: {
      storefront_confirmation_sha256: "d".repeat(64),
      storefront_fulfillment_promise: orderPromise,
    },
  };
  const query = { graph: jest.fn(async () => ({ data: [order] })) };
  const orderModule = { updateOrders: jest.fn(async ([updated]: { id: string; metadata: Record<string, unknown> }[]) => {
    order.metadata = updated.metadata;
  }) };
  const container = lockedContainer((key) => key === ContainerRegistrationKeys.QUERY ? query : key === Modules.ORDER ? orderModule : undefined);
  const statusEvent = event({ event_id: "e3cc872d-6d49-4f7a-81ce-a9d5768530f0" });
  const fetcher = jest.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      expect(order.metadata.storefront_fulfillment_status.status).toBe("ready_for_collection");
      return { ok: true, json: async () => ({ acknowledged: 1 }) } as Response;
    }
    return { ok: true, json: async () => ({ items: [statusEvent] }) } as Response;
  });

  try {
    await expect(syncStorefrontFulfillmentEvents(container, fetcher)).resolves.toEqual({ received: 1, acknowledged: 1 });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][1]?.method).toBe("POST");
  } finally {
    for (const [name, value] of [
      ["FIRSTOUT_OPS_URL", previous.url],
      ["FIRSTOUT_OPS_TOKEN", previous.token],
      ["FIRSTOUT_OPS_COMPANY_ID", previous.company],
    ] as const) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
});

test("leaves a message pending when Medusa cannot persist its status", async () => {
  const previous = {
    url: process.env.FIRSTOUT_OPS_URL,
    token: process.env.FIRSTOUT_OPS_TOKEN,
    company: process.env.FIRSTOUT_OPS_COMPANY_ID,
  };
  process.env.FIRSTOUT_OPS_URL = "http://firstout.test/api/v1/ops-commerce/v1";
  process.env.FIRSTOUT_OPS_TOKEN = "test-service-token";
  process.env.FIRSTOUT_OPS_COMPANY_ID = "company-test";
  const order = {
    id: "order_test123",
    display_id: 753,
    email: "customer@example.test",
    metadata: {
      storefront_confirmation_sha256: "e".repeat(64),
      storefront_fulfillment_promise: orderPromise,
    },
  };
  const query = { graph: jest.fn(async () => ({ data: [order] })) };
  const orderModule = { updateOrders: jest.fn(async () => { throw new Error("database_unavailable"); }) };
  const container = lockedContainer((key) => key === ContainerRegistrationKeys.QUERY ? query : key === Modules.ORDER ? orderModule : undefined);
  const warning = jest.spyOn(console, "warn").mockImplementation(() => {});
  const fetcher = jest.fn(async (_input: RequestInfo | URL, init?: RequestInit) => init?.method === "POST"
    ? { ok: true, json: async () => ({ acknowledged: 1 }) } as Response
    : { ok: true, json: async () => ({ items: [event({ event_id: "9c6ab4b8-71dc-4db7-8a84-2f7cb59a66f0" })] }) } as Response);

  try {
    await expect(syncStorefrontFulfillmentEvents(container, fetcher)).resolves.toEqual({ received: 1, acknowledged: 0 });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1]?.method).toBeUndefined();
  } finally {
    warning.mockRestore();
    for (const [name, value] of [
      ["FIRSTOUT_OPS_URL", previous.url],
      ["FIRSTOUT_OPS_TOKEN", previous.token],
      ["FIRSTOUT_OPS_COMPANY_ID", previous.company],
    ] as const) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  }
});

test("keeps a failed confirmation durable and retries it without repeating order effects", async () => {
  const oldBffSecret = process.env.STOREFRONT_BFF_SECRET;
  const oldPublicUrl = process.env.STOREFRONT_PUBLIC_URL;
  process.env.STOREFRONT_BFF_SECRET = "storefront-test-secret-with-more-than-32-characters";
  process.env.STOREFRONT_PUBLIC_URL = "http://localhost:3004";
  const order: Record<string, any> = {
    id: "order_test123",
    display_id: 753,
    email: "customer@example.test",
    currency_code: "zar",
    created_at: "2026-09-29T10:00:00.000Z",
    items: [],
    metadata: {
      storefront_confirmation_sha256: "b".repeat(64),
      storefront_fulfillment_promise: orderPromise,
    },
  };
  const query = { graph: jest.fn(async ({ filters }: { filters?: { id: string } }) => ({
    data: filters ? [order] : order.id === "order_test123" ? [{ id: order.id }] : [],
  })) };
  const orderModule = { updateOrders: jest.fn(async ([updated]: { id: string; metadata: Record<string, unknown> }[]) => {
    order.metadata = updated.metadata;
  }) };
  const createNotifications = jest.fn()
    .mockRejectedValueOnce(new Error("mail_transport_unavailable"))
    .mockResolvedValueOnce({ id: "notification-test" });
  const notificationModule = { createNotifications };
  const makeContainer = () => lockedContainer((key) => key === ContainerRegistrationKeys.QUERY ? query
    : key === Modules.ORDER ? orderModule
    : key === Modules.NOTIFICATION ? notificationModule
    : undefined);

  try {
    await retryStorefrontOrderNotifications(makeContainer(), new Date());
    expect(order.metadata.storefront_notification_outbox[0]).toMatchObject({
      id: "confirmation:order_test123",
      status: "retry_wait",
      failure_code: "mail_transport_unavailable",
    });
    expect(createNotifications).toHaveBeenCalledTimes(1);
    const sentData = createNotifications.mock.calls[0][0].data;
    expect(sentData.order_access_url).toContain("#order_id=order_test123&access=");
    expect(JSON.stringify(order.metadata.storefront_notification_outbox)).not.toContain("order_access_url");
    expect(JSON.stringify(order.metadata.storefront_notification_outbox)).not.toContain("b".repeat(64));

    // A fresh container represents a restarted Medusa worker; only the order's
    // persisted outbox survives between attempts.
    await retryStorefrontOrderNotifications(makeContainer(), new Date(Date.now() + 15_000));
    expect(order.metadata.storefront_notification_outbox[0].status).toBe("sent");
    expect(createNotifications).toHaveBeenCalledTimes(2);
  } finally {
    if (oldBffSecret === undefined) delete process.env.STOREFRONT_BFF_SECRET;
    else process.env.STOREFRONT_BFF_SECRET = oldBffSecret;
    if (oldPublicUrl === undefined) delete process.env.STOREFRONT_PUBLIC_URL;
    else process.env.STOREFRONT_PUBLIC_URL = oldPublicUrl;
  }
});
