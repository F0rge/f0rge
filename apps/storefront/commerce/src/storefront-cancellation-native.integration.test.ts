import { randomUUID } from "node:crypto";
import path from "node:path";
import { medusaIntegrationTestRunner } from "@medusajs/test-utils";
import { updateProductVariantsWorkflow } from "@medusajs/medusa/core-flows";
import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { availableCapacity, consumeCapacity, mergeCapacityState, reserveCapacity } from "./made-to-order-capacity";
import { recordCustomerRefundStatus } from "./storefront-peach-refunds";
import { syncStorefrontFulfillmentEvents, type StorefrontFulfillmentEvent } from "./storefront-fulfillment-events";
import type { PeachWebhookEvent } from "./peach-checkout";

type JsonRecord = Record<string, any>;

const liveTestRequested = process.env.STOREFRONT_NATIVE_CANCELLATION_LIVE_TEST === "1";

function isLoopbackHost(hostname: string): boolean {
  return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(hostname.toLowerCase());
}

function isLoopbackUrl(value: string | undefined): boolean {
  if (!value?.trim()) return false;
  try {
    return isLoopbackHost(new URL(value).hostname);
  } catch {
    return false;
  }
}

if (liveTestRequested) {
  if (!process.env.DATABASE_URL?.trim() || !process.env.DB_HOST?.trim() || !process.env.REDIS_URL?.trim()) {
    throw new Error("storefront_native_cancellation_local_test_environment_incomplete");
  }
  if (!isLoopbackHost(process.env.DB_HOST) || !isLoopbackUrl(process.env.DATABASE_URL) ||
      !isLoopbackUrl(process.env.REDIS_URL)) {
    throw new Error("storefront_native_cancellation_test_refuses_nonlocal_services");
  }
}

const liveTestEnabled = liveTestRequested;
const testCompanyId = randomUUID();
const testServiceToken = "synthetic-cancellation-ops-token";
const testOpsUrl = "http://firstout-cancellation.fixture.test/api/v1/ops-commerce/v1";
const testPeachEnvironment = {
  PEACH_ENVIRONMENT: "sandbox",
  PEACH_CLIENT_ID: "synthetic-cancellation-client",
  PEACH_CLIENT_SECRET: "synthetic-cancellation-client-secret",
  PEACH_MERCHANT_ID: "synthetic-cancellation-merchant",
  PEACH_ENTITY_ID: "synthetic-cancellation-entity",
  PEACH_WEBHOOK_SECRET: "synthetic-cancellation-webhook-secret",
  PEACH_CHECKOUT_SECRET: "synthetic-cancellation-checkout-secret",
  PEACH_WEBHOOK_URL: "https://localhost:9000/hooks/peach",
  STOREFRONT_PUBLIC_URL: "https://localhost:3004",
  FIRSTOUT_OPS_URL: testOpsUrl,
  FIRSTOUT_OPS_TOKEN: testServiceToken,
  FIRSTOUT_OPS_COMPANY_ID: testCompanyId,
};
const originalFetch = globalThis.fetch.bind(globalThis);
jest.setTimeout(180_000);

function requestUrl(input: RequestInfo | URL): URL {
  return new URL(typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url);
}

function response(value: unknown): Response {
  return new Response(JSON.stringify(value), { status: 200, headers: { "content-type": "application/json" } });
}

if (liveTestEnabled) {
  Object.assign(process.env, testPeachEnvironment);
  // The runner's scheduled work is allowed to use local fixtures only. In
  // particular, this cancellation proof never sends an external provider call.
  globalThis.fetch = async (input, init) => {
    const url = requestUrl(input);
    if (url.hostname.endsWith("peachpayments.com")) {
      throw new Error("native cancellation test blocks provider requests");
    }
    if (url.hostname === "firstout-cancellation.fixture.test") {
      if (url.pathname.endsWith("/refund-commands")) return response({ items: [] });
      throw new Error("native cancellation test requires an explicit Firstout fixture feed");
    }
    return originalFetch(input, init);
  };

  const appPath = path.resolve(__dirname, "..");
  medusaIntegrationTestRunner({
    moduleName: `storefront-cancellation-native-${randomUUID().replaceAll("-", "").slice(0, 10)}`,
    cwd: appPath,
    medusaConfigFile: appPath,
    env: { NODE_ENV: "test", ...testPeachEnvironment },
    testSuite: ({ getContainer }) => {
      describe("accepted Firstout cancellation against native Medusa PostgreSQL", () => {
        let container: MedusaContainer;
        let orderId: string;
        let mtoVariantId: string;
        let stockedVariantId: string;
        let mtoLineId: string;
        let stockedLineId: string;
        let offerId: string;
        let orderPromise: JsonRecord;
        let cancellation: StorefrontFulfillmentEvent;
        let ackedIds: string[];
        let otherMtoCommitmentId: string;
        let unrelatedReleaseHistory: JsonRecord;

        const getOrder = async (): Promise<JsonRecord> => {
          const query = container.resolve(ContainerRegistrationKeys.QUERY) as unknown as {
            graph(input: JsonRecord): Promise<{ data: JsonRecord[] }>;
          };
          const { data } = await query.graph({
            entity: "order",
            fields: [
              "id", "status", "canceled_at", "metadata",
              "items.id", "items.variant.id", "items.variant.metadata",
            ],
            filters: { id: orderId },
          });
          const order = data[0];
          if (!order) throw new Error("native_cancellation_test_order_missing");
          return order;
        };

        const getVariants = async (): Promise<Map<string, JsonRecord>> => {
          const order = await getOrder();
          const items = Array.isArray(order.items) ? order.items as JsonRecord[] : [];
          return new Map(items.map((item) => [
            String(item.variant.id), item.variant as JsonRecord,
          ]));
        };

        const deliverAcceptedEvent = async (): Promise<void> => {
          ackedIds = [];
          const fetcher: typeof fetch = async (input, init) => {
            const url = requestUrl(input);
            const headers = init?.headers as Record<string, string>;
            expect(headers.authorization).toBe(`Bearer ${testServiceToken}`);
            expect(headers["x-ops-company-id"]).toBe(testCompanyId);
            if (url.pathname.endsWith("/fulfillment-events") && init?.method !== "POST") {
              expect(url.search).toBe("?limit=100");
              return response({ items: [cancellation] });
            }
            if (url.pathname.endsWith("/fulfillment-events/ack") && init?.method === "POST") {
              ackedIds = (JSON.parse(String(init.body)) as { event_ids: string[] }).event_ids;
              return response({ acknowledged: ackedIds.length });
            }
            throw new Error("native_cancellation_test_unexpected_ops_request");
          };
          await expect(syncStorefrontFulfillmentEvents(container, fetcher)).resolves.toEqual({
            received: 1,
            acknowledged: 1,
          });
          expect(ackedIds).toEqual([cancellation.event_id]);
        };

        beforeAll(async () => {
          container = getContainer();
          const suffix = randomUUID().replaceAll("-", "").slice(0, 12);
          const email = `native-cancel-${suffix}@example.test`;
          offerId = randomUUID();
          orderPromise = {
            version: 1,
            kind: "stocked",
            accepted_at: new Date().toISOString(),
            estimated_from: new Date().toISOString().slice(0, 10),
            estimated_by: new Date().toISOString().slice(0, 10),
          };
          const confirmationDigest = "c".repeat(64);
          unrelatedReleaseHistory = {
            event_id: randomUUID(),
            commitment_id: `storefront:older-${suffix}:older-line`,
            pending_paid_quantity: 1,
            made_to_order_quantity: 0,
            recorded_at: new Date().toISOString(),
          };

          const productModule = container.resolve(Modules.PRODUCT) as unknown as {
            createProducts(input: JsonRecord): Promise<JsonRecord | JsonRecord[]>;
          };
          const productResult = await productModule.createProducts({
            title: `Synthetic cancellation product ${suffix}`,
            handle: `synthetic-cancellation-${suffix.toLowerCase()}`,
            status: "published",
            options: [{ title: "Fulfillment", values: ["Made to order", "Stocked"] }],
            variants: [
              {
                title: "Made to order",
                sku: `CANCEL-MTO-${suffix}`,
                manage_inventory: false,
                options: { Fulfillment: "Made to order" },
              },
              {
                title: "Stocked",
                sku: `CANCEL-STOCK-${suffix}`,
                manage_inventory: false,
                options: { Fulfillment: "Stocked" },
              },
            ],
          });
          const product = Array.isArray(productResult) ? productResult[0] : productResult;
          const variants = Array.isArray(product?.variants) ? product.variants as JsonRecord[] : [];
          const mtoVariant = variants.find((variant) => variant.title === "Made to order");
          const stockedVariant = variants.find((variant) => variant.title === "Stocked");
          if (typeof mtoVariant?.id !== "string" || typeof stockedVariant?.id !== "string") {
            throw new Error("native_cancellation_test_product_variants_missing");
          }
          mtoVariantId = mtoVariant.id;
          stockedVariantId = stockedVariant.id;

          const orderModule = container.resolve(Modules.ORDER) as unknown as {
            createOrders(input: JsonRecord): Promise<JsonRecord[] | JsonRecord>;
            createOrderLineItems(orderId: string, items: JsonRecord[]): Promise<JsonRecord[]>;
            updateOrders(rows: JsonRecord[]): Promise<unknown>;
            cancel(orderId: string): Promise<unknown>;
          };
          const orderResult = await orderModule.createOrders({
            currency_code: "zar",
            email,
            status: "completed",
            metadata: {
              storefront_confirmation_sha256: confirmationDigest,
              storefront_fulfillment_promise: orderPromise,
              storefront_checkout: { fulfillment_type: "collection" },
            },
          });
          const order = Array.isArray(orderResult) ? orderResult[0] : orderResult;
          if (typeof order?.id !== "string") throw new Error("native_cancellation_test_order_create_failed");
          orderId = order.id;
          const items = await orderModule.createOrderLineItems(orderId, [
            {
              title: "Synthetic MTO order line",
              quantity: 1,
              unit_price: 100,
              is_tax_inclusive: true,
              requires_shipping: false,
              product_id: product.id,
              variant_id: mtoVariantId,
              metadata: { fulfillment_promise: { kind: "made_to_order", offer_id: offerId } },
            },
            {
              title: "Synthetic stocked order line",
              quantity: 2,
              unit_price: 50,
              is_tax_inclusive: true,
              requires_shipping: false,
              product_id: product.id,
              variant_id: stockedVariantId,
              metadata: { fulfillment_promise: { kind: "stocked" } },
            },
          ]);
          const mtoItem = items.find((item) => item.variant_id === mtoVariantId) || items[0];
          const stockedItem = items.find((item) => item.variant_id === stockedVariantId) || items[1];
          if (typeof mtoItem?.id !== "string" || typeof stockedItem?.id !== "string") {
            throw new Error("native_cancellation_test_order_items_missing");
          }
          mtoLineId = mtoItem.id;
          stockedLineId = stockedItem.id;
          await orderModule.updateOrders([{
            id: orderId,
            metadata: {
              ...order.metadata,
              storefront_handoff_outbox: { status: "imported", payload: { external_order_id: orderId } },
            },
          }]);

          const acceptedAt = new Date();
          const expiresAt = new Date(Date.now() + 30 * 86400_000).toISOString();
          otherMtoCommitmentId = `storefront:other-${suffix}:other-mto`;
          const offer = {
            id: offerId,
            capacity: 2,
            min_lead_time_days: 28,
            max_lead_time_days: 42,
            expires_at: expiresAt,
          };
          let capacityState = mergeCapacityState(null, offer, new Date().toISOString());
          capacityState = reserveCapacity(
            capacityState, offerId, `cart-${suffix}`, "mto", 1,
            new Date(Date.now() + 10 * 60_000).toISOString(), acceptedAt,
          );
          capacityState = consumeCapacity(
            capacityState, offerId, `cart-${suffix}`, "mto", `storefront:${orderId}:${mtoLineId}`,
            1, Date.now(),
          );
          capacityState = reserveCapacity(
            capacityState, offerId, `other-cart-${suffix}`, "mto", 1,
            new Date(Date.now() + 10 * 60_000).toISOString(), acceptedAt,
          );
          capacityState = consumeCapacity(
            capacityState, offerId, `other-cart-${suffix}`, "mto", otherMtoCommitmentId,
            1, Date.now(),
          );

          await updateProductVariantsWorkflow(container).run({
            input: {
              product_variants: [
                {
                  id: mtoVariantId,
                  metadata: {
                    source_sku_id: randomUUID(),
                    source_observed_at: new Date().toISOString(),
                    storefront_made_to_order_capacity: capacityState,
                    storefront_cancellation_releases: [unrelatedReleaseHistory],
                    pending_paid_commitments: [
                      { commitment_id: `storefront:${orderId}:${mtoLineId}`, source_sku_id: randomUUID(), quantity: 1 },
                      { commitment_id: otherMtoCommitmentId, source_sku_id: randomUUID(), quantity: 3 },
                    ],
                  },
                },
                {
                  id: stockedVariantId,
                  metadata: {
                    source_sku_id: randomUUID(),
                    storefront_cancellation_releases: [unrelatedReleaseHistory],
                    pending_paid_commitments: [
                      { commitment_id: `storefront:${orderId}:${stockedLineId}`, source_sku_id: randomUUID(), quantity: 2 },
                      { commitment_id: `storefront:other-${suffix}:other-stock`, source_sku_id: randomUUID(), quantity: 4 },
                    ],
                  },
                },
              ],
            },
          });

          const now = new Date().toISOString();
          cancellation = {
            event_id: randomUUID(),
            company_id: testCompanyId,
            external_order_id: orderId,
            revision: 1,
            fulfillment_type: "collection",
            status: "cancelled",
            fulfillment_promise: orderPromise,
            occurred_at: now,
          };
        });

        afterAll(() => {
          globalThis.fetch = originalFetch;
        });

        test("verified refund status alone preserves stock; accepted cancellation cancels once and releases only its commitments", async () => {
          const initialVariants = await getVariants();
          const initialMto = initialVariants.get(mtoVariantId)!;
          expect(availableCapacity(
            initialMto.metadata.storefront_made_to_order_capacity.allocations[offerId], Date.now(),
          )).toBe(0);

          const providerRefund: PeachWebhookEvent = {
            webhook_id: "synthetic-verified-refund",
            checkout_id: "",
            merchant_reference: "",
            amount_minor: 100,
            currency_code: "ZAR",
            payment_type: "RF",
            result_code: "000.100.110",
            transaction_id: randomUUID().replaceAll("-", ""),
            referenced_transaction_id: randomUUID().replaceAll("-", ""),
            refund_request_id: null,
            event_timestamp: new Date().toISOString(),
            raw_sha256: "a".repeat(64),
            canonical_sha256: "b".repeat(64),
          };
          await recordCustomerRefundStatus(container, orderId, providerRefund, "succeeded");
          const afterRefundVariants = await getVariants();
          expect(afterRefundVariants.get(mtoVariantId)?.metadata.pending_paid_commitments).toEqual(
            initialMto.metadata.pending_paid_commitments,
          );
          expect(afterRefundVariants.get(mtoVariantId)?.metadata.storefront_cancellation_releases)
            .toEqual([unrelatedReleaseHistory]);
          expect(afterRefundVariants.get(stockedVariantId)?.metadata.storefront_cancellation_releases)
            .toEqual([unrelatedReleaseHistory]);
          expect(availableCapacity(
            afterRefundVariants.get(mtoVariantId)?.metadata.storefront_made_to_order_capacity.allocations[offerId],
            Date.now(),
          )).toBe(0);
          expect((await getOrder()).status).toBe("completed");

          const orderModule = container.resolve(Modules.ORDER) as unknown as {
            cancel(orderId: string): Promise<unknown>;
          };
          const cancelSpy = jest.spyOn(orderModule, "cancel");
          await deliverAcceptedEvent();

          const canceledOrder = await getOrder();
          expect(canceledOrder.status).toBe("canceled");
          expect(canceledOrder.canceled_at).toBeTruthy();
          expect(canceledOrder.metadata.storefront_fulfillment_status).toMatchObject({
            status: "cancelled",
            revision: cancellation.revision,
            event_id: cancellation.event_id,
          });
          const canceledAt = canceledOrder.canceled_at;
          const canceledVariants = await getVariants();
          const canceledMto = canceledVariants.get(mtoVariantId)!;
          const canceledStocked = canceledVariants.get(stockedVariantId)!;
          expect(canceledMto.metadata.pending_paid_commitments).toEqual([
            expect.objectContaining({ commitment_id: otherMtoCommitmentId, quantity: 3 }),
          ]);
          expect(canceledStocked.metadata.pending_paid_commitments).toEqual([
            expect.objectContaining({ commitment_id: expect.stringMatching(/^storefront:other-.*:other-stock$/), quantity: 4 }),
          ]);
          expect(canceledMto.metadata.storefront_made_to_order_capacity.allocations[offerId].committed)
            .toEqual({ [otherMtoCommitmentId]: 1 });
          expect(availableCapacity(
            canceledMto.metadata.storefront_made_to_order_capacity.allocations[offerId], Date.now(),
          )).toBe(1);
          expect(canceledMto.metadata.storefront_cancellation_releases).toEqual([
            unrelatedReleaseHistory,
            expect.objectContaining({
              event_id: cancellation.event_id,
              commitment_id: `storefront:${orderId}:${mtoLineId}`,
              pending_paid_quantity: 1,
              made_to_order_quantity: 1,
            }),
          ]);
          expect(canceledStocked.metadata.storefront_cancellation_releases).toEqual([
            unrelatedReleaseHistory,
            expect.objectContaining({
              event_id: cancellation.event_id,
              commitment_id: `storefront:${orderId}:${stockedLineId}`,
              pending_paid_quantity: 2,
              made_to_order_quantity: 0,
            }),
          ]);
          expect(cancelSpy).toHaveBeenCalledTimes(1);

          await deliverAcceptedEvent();
          const replayedOrder = await getOrder();
          expect(replayedOrder.status).toBe("canceled");
          expect(replayedOrder.canceled_at).toEqual(canceledAt);
          expect(cancelSpy).toHaveBeenCalledTimes(1);
          const replayedVariants = await getVariants();
          expect(replayedVariants.get(mtoVariantId)?.metadata.storefront_cancellation_releases)
            .toEqual(canceledMto.metadata.storefront_cancellation_releases);
          expect(replayedVariants.get(stockedVariantId)?.metadata.storefront_cancellation_releases)
            .toEqual(canceledStocked.metadata.storefront_cancellation_releases);
          cancelSpy.mockRestore();
        }, 180_000);
      });
    },
  });
} else {
  describe.skip("native Medusa cancellation integration", () => {
    test.skip("requires the disposable native Medusa PostgreSQL environment", () => undefined);
  });
}
