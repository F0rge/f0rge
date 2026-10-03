import { createHash, createHmac, randomUUID } from "node:crypto";
import path from "node:path";
import { medusaIntegrationTestRunner } from "@medusajs/test-utils";
import { createOrderPaymentCollectionWorkflow } from "@medusajs/core-flows";
import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { PEACH_PAYMENT_PROVIDER_ID } from "./peach-payment-config";
import { PEACH_REFUND_URL, parsePeachRefundResponse, peachCheckoutSignature, type PeachRefundObservation } from "./peach-refunds";
import { createPeachAttempt, updatePeachAttempt } from "./peach-payment-store";
import {
  persistAndProcessRefundObservation, syncStorefrontPeachRefundCommands,
} from "./storefront-peach-refunds";

type JsonRecord = Record<string, unknown>;

const requiredEnv = [
  "DATABASE_URL", "DB_HOST", "REDIS_URL", "STOREFRONT_FIRSTOUT_API_URL", "FIRSTOUT_OPS_URL",
  "FIRSTOUT_OPS_TOKEN", "FIRSTOUT_OPS_COMPANY_ID", "FIRSTOUT_OWNER_EMAIL", "FIRSTOUT_OWNER_PASSWORD",
] as const;
const liveTestRequested = process.env.STOREFRONT_NATIVE_REFUND_LIVE_TEST === "1";

function isLoopbackHost(hostname: string): boolean {
  return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(hostname.toLowerCase());
}

function isLoopbackUrl(value: string | undefined, rejectCredentials = false): boolean {
  if (!value?.trim()) return false;
  try {
    const url = new URL(value);
    return isLoopbackHost(url.hostname) && (!rejectCredentials || (!url.username && !url.password));
  } catch {
    return false;
  }
}

if (liveTestRequested) {
  const missing = requiredEnv.filter((key) => !process.env[key]?.trim());
  if (missing.length) throw new Error("storefront_native_refund_local_test_environment_incomplete");
  if (!isLoopbackHost(process.env.DB_HOST!) || !isLoopbackUrl(process.env.DATABASE_URL) ||
      !isLoopbackUrl(process.env.REDIS_URL) || !isLoopbackUrl(process.env.STOREFRONT_FIRSTOUT_API_URL, true) ||
      !isLoopbackUrl(process.env.FIRSTOUT_OPS_URL, true)) {
    throw new Error("storefront_native_refund_test_refuses_nonlocal_services");
  }
}

const liveTestEnabled = liveTestRequested;
const testCheckoutSecret = "local-refund-integration-only-hmac-secret";
const testBffSecret = "local-refund-integration-only-order-status-secret";
const testPeachEnvironment = {
  PEACH_ENVIRONMENT: "sandbox",
  PEACH_CLIENT_ID: "synthetic-integration-client",
  PEACH_CLIENT_SECRET: "synthetic-integration-client-secret",
  PEACH_MERCHANT_ID: "synthetic-integration-merchant",
  PEACH_ENTITY_ID: "synthetic-integration-entity",
  PEACH_WEBHOOK_SECRET: "synthetic-integration-webhook-secret",
  PEACH_CHECKOUT_SECRET: testCheckoutSecret,
  STOREFRONT_BFF_SECRET: testBffSecret,
  PEACH_WEBHOOK_URL: "http://localhost:9000/hooks/peach",
  STOREFRONT_PUBLIC_URL: "http://localhost:3004",
};
const originalFetch = globalThis.fetch.bind(globalThis);
jest.setTimeout(180_000);

function requestUrl(input: RequestInfo | URL): URL {
  return new URL(typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url);
}

if (liveTestEnabled) {
  // The Medusa integration runner starts scheduled jobs. Their refund feed is
  // deliberately empty here, and every accidental Peach HTTP call is blocked.
  Object.assign(process.env, testPeachEnvironment);
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (url.hostname.endsWith("peachpayments.com")) return new Response("sandbox transport disabled in native integration test", { status: 503 });
    if (url.pathname.endsWith("/refund-commands") && url.search === "?limit=100") {
      return new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return originalFetch(input, init);
  };
}

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function responseObject(value: unknown): JsonRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("storefront_refund_test_response_invalid");
  return value as JsonRecord;
}

function medusaMajorAmount(value: unknown): number {
  const raw = record(value);
  return Number(raw.value ?? value);
}

async function firstoutJson(pathname: string, init: RequestInit, expectedStatus: number): Promise<JsonRecord> {
  const base = process.env.STOREFRONT_FIRSTOUT_API_URL!.replace(/\/+$/, "");
  const response = await originalFetch(`${base}${pathname}`, init);
  if (response.status !== expectedStatus) {
    const body = record(await response.clone().json().catch(() => null));
    const detail = typeof body.detail === "string" && /^[A-Za-z0-9_. -]{1,100}$/.test(body.detail)
      ? `_${body.detail.replaceAll(" ", "_")}` : "";
    throw new Error(`firstout_${pathname.replaceAll("/", "_")}_http_${response.status}${detail}`);
  }
  return responseObject(await response.json());
}

async function createFirstoutMtoHandoff(externalOrderId: string, captureId: string): Promise<string> {
  const ownerHeaders = { ...(await firstoutOwnerCookieHeaders()), "content-type": "application/json" };

  const suffix = randomUUID().replaceAll("-", "").slice(0, 12).toUpperCase();
  const skuRef = `REFUND-NATIVE-${suffix}`;
  const sku = await firstoutJson("/api/v1/skus", {
    method: "POST",
    headers: ownerHeaders,
    body: JSON.stringify({
      our_ref: skuRef,
      our_barcode: `${skuRef}-BAR`,
      name: `Synthetic native refund integration chair ${suffix}`,
      design: `Synthetic integration chair ${suffix}`,
      fabric: "Oak",
    }),
  }, 201);
  const now = new Date();
  const offer = await firstoutJson(`/api/v1/skus/${String(sku.id)}`, {
    method: "PATCH",
    headers: ownerHeaders,
    body: JSON.stringify({
      retail_inc_vat: "1150.00",
      storefront_published: true,
      made_to_order_capacity: 100,
      made_to_order_lead_time_min_days: 28,
      made_to_order_lead_time_max_days: 42,
      made_to_order_expires_at: new Date(now.getTime() + 7 * 86400_000).toISOString(),
    }),
  }, 200);
  const estimatedFrom = new Date(now.getTime() + 28 * 86400_000).toISOString().slice(0, 10);
  const estimatedBy = new Date(now.getTime() + 42 * 86400_000).toISOString().slice(0, 10);
  const linePromise = {
    kind: "made_to_order",
    offer_id: offer.made_to_order_offer_id,
    min_lead_time_days: 28,
    max_lead_time_days: 42,
    estimated_from: estimatedFrom,
    estimated_by: estimatedBy,
    expires_at: offer.made_to_order_expires_at,
  };
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID!;
  const imported = await firstoutJson("/api/v1/ops-commerce/v1/orders", {
    method: "POST",
    headers: {
      authorization: `Bearer ${process.env.FIRSTOUT_OPS_TOKEN}`,
      "x-ops-company-id": companyId,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      company_id: companyId,
      channel: "storefront",
      external_order_id: externalOrderId,
      external_payment_id: `synthetic-payment-${captureId}`,
      correlation_id: `storefront:${externalOrderId}`,
      currency_code: "ZAR",
      customer: {
        external_id: `synthetic-customer-${suffix}`,
        name: "Synthetic refund integration customer",
        email: `refund-native-${suffix.toLowerCase()}@example.test`,
        phone: "+27110000001",
        billing_address: "1 Synthetic Test Street, Johannesburg, 2000",
      },
      fulfillment: {
        type: "collection",
        reference: `synthetic-collection-${suffix}`,
        recipient: "Synthetic refund integration customer",
        address: {
          address_1: "1 Synthetic Test Street",
          address_2: "",
          city: "Johannesburg",
          province: "Gauteng",
          postal_code: "2000",
          country_code: "za",
        },
        fee_ex_minor_zar: 0,
        fee_vat_minor_zar: 0,
        fee_total_minor_zar: 0,
      },
      lines: [{
        external_line_id: "line-1",
        source_sku_id: sku.id,
        sku: skuRef,
        title: "Synthetic native refund integration chair",
        quantity: 1,
        unit_ex_minor_zar: 100000,
        ex_minor_zar: 100000,
        vat_minor_zar: 15000,
        total_minor_zar: 115000,
        fulfillment_promise: linePromise,
      }],
      totals: {
        subtotal_ex_minor_zar: 100000,
        tax_minor_zar: 15000,
        delivery_ex_minor_zar: 0,
        delivery_tax_minor_zar: 0,
        delivery_total_minor_zar: 0,
        total_minor_zar: 115000,
      },
      payment: {
        provider: "peach",
        reference: captureId,
        captured_at: now.toISOString(),
        amount_minor_zar: 115000,
        currency_code: "ZAR",
      },
      fulfillment_promise: {
        version: 1,
        kind: "made_to_order",
        accepted_at: now.toISOString(),
        estimated_from: estimatedFrom,
        estimated_by: estimatedBy,
      },
    }),
  }, 201);
  if (imported.status !== "imported" || typeof imported.id !== "string") throw new Error("firstout_synthetic_handoff_import_failed");
  return imported.id;
}

type RefundSimulator = {
  fetcher: typeof fetch;
  observations: PeachRefundObservation[];
  eventResponses: JsonRecord[];
  eventRequests: JsonRecord[];
  providerRequests: JsonRecord[];
};

function peachSimulator(): RefundSimulator {
  const observations: PeachRefundObservation[] = [];
  const eventResponses: JsonRecord[] = [];
  const eventRequests: JsonRecord[] = [];
  const providerRequests: JsonRecord[] = [];
  const fetcher: typeof fetch = async (input, init) => {
    const url = requestUrl(input);
    if (url.toString() === PEACH_REFUND_URL) {
      const request = JSON.parse(String(init?.body)) as JsonRecord;
      providerRequests.push(request);
      const responseBody = {
        id: randomUUID().replaceAll("-", ""),
        referencedId: String(request.id),
        amount: String(request.amount),
        currency: String(request.currency),
        paymentType: "RF",
        timestamp: new Date().toISOString(),
        result: { code: "000.100.110" },
      };
      const signature = peachCheckoutSignature({
        id: responseBody.id,
        referencedId: responseBody.referencedId,
        amount: responseBody.amount,
        currency: responseBody.currency,
        paymentType: responseBody.paymentType,
        timestamp: responseBody.timestamp,
        "result.code": responseBody.result.code,
      }, testCheckoutSecret);
      const signed = { ...responseBody, signature };
      const observation = parsePeachRefundResponse(signed, testCheckoutSecret, {
        referencedCaptureId: responseBody.referencedId,
        amountMinor: Math.round(Number(responseBody.amount) * 100),
        currencyCode: responseBody.currency,
      });
      if (!observation) throw new Error("synthetic_peach_response_failed_signature_validation");
      observations.push(observation);
      return new Response(JSON.stringify(signed), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (url.pathname.endsWith("/refund-events")) {
      eventRequests.push(record(JSON.parse(String(init?.body))));
    }
    const response = await originalFetch(input, init);
    if (url.pathname.endsWith("/refund-events")) {
      eventResponses.push(responseObject(await response.clone().json()));
    }
    return response;
  };
  return { fetcher, observations, eventResponses, eventRequests, providerRequests };
}

function customerStatusToken(orderId: string, confirmationDigest: string): string {
  return createHmac("sha256", testBffSecret)
    .update(`storefront-order-status:v1:${orderId}:${confirmationDigest}`)
    .digest("base64url");
}

function eventFromObservation(observation: PeachRefundObservation, requestId: string) {
  return {
    webhook_id: `synthetic-duplicate-${randomUUID()}`,
    checkout_id: "",
    merchant_reference: "",
    amount_minor: observation.amount_minor,
    currency_code: observation.currency_code,
    payment_type: "RF",
    result_code: observation.result_code,
    transaction_id: observation.provider_refund_id,
    referenced_transaction_id: observation.referenced_capture_id,
    refund_request_id: requestId,
    event_timestamp: observation.event_timestamp,
    raw_sha256: observation.canonical_sha256,
    canonical_sha256: observation.canonical_sha256,
  };
}

if (liveTestEnabled) {
  const appPath = path.resolve(__dirname, "..");
  medusaIntegrationTestRunner({
    moduleName: `storefront-refund-native-${randomUUID().replaceAll("-", "").slice(0, 10)}`,
    cwd: appPath,
    medusaConfigFile: appPath,
    env: {
      NODE_ENV: "test",
      ...testPeachEnvironment,
      FIRSTOUT_OPS_URL: process.env.FIRSTOUT_OPS_URL!,
      FIRSTOUT_OPS_TOKEN: process.env.FIRSTOUT_OPS_TOKEN!,
      FIRSTOUT_OPS_COMPANY_ID: process.env.FIRSTOUT_OPS_COMPANY_ID!,
    },
    testSuite: ({ getContainer, api }) => {
      describe("native Medusa refund convergence against isolated Firstout HTTP", () => {
        let container: MedusaContainer;
        let db: Knex;
        let orderId: string;
        let paymentId: string;
        let paymentCollectionId: string;
        let captureId: string;
        let handoffId: string;
        let statusToken: string;
        let publishableApiKey: string;
        let simulator: RefundSimulator;

        beforeAll(async () => {
          container = getContainer();
          db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION) as Knex;
          simulator = peachSimulator();

          const apiKeyModule = container.resolve(Modules.API_KEY) as unknown as {
            createApiKeys(input: JsonRecord): Promise<JsonRecord>;
          };
          const apiKey = await apiKeyModule.createApiKeys({
            type: "publishable",
            title: "Native refund integration",
            created_by: "native-refund-integration",
          });
          if (typeof apiKey.token !== "string") throw new Error("medusa_native_test_publishable_key_create_failed");
          publishableApiKey = apiKey.token;

          const orderModule = container.resolve(Modules.ORDER) as unknown as {
            createOrders(input: JsonRecord): Promise<JsonRecord[] | JsonRecord>;
            addOrderTransactions(rows: JsonRecord[]): Promise<JsonRecord[]>;
            updateOrders(rows: JsonRecord[]): Promise<unknown>;
          };
          const paymentModule = container.resolve(Modules.PAYMENT) as unknown as {
            createPaymentSession_(collectionId: string, input: JsonRecord): Promise<JsonRecord>;
            updatePaymentSession(input: JsonRecord): Promise<JsonRecord>;
            authorizePaymentSession(id: string, context: JsonRecord): Promise<JsonRecord | null>;
            retrievePayment(id: string, config: JsonRecord): Promise<JsonRecord>;
            retrievePaymentCollection(id: string, config: JsonRecord): Promise<JsonRecord>;
          };
          const email = `medusa-refund-${randomUUID()}@example.test`;
          const fulfillmentPromise = {
            version: 1,
            kind: "made_to_order",
            accepted_at: new Date().toISOString(),
            estimated_from: new Date(Date.now() + 28 * 86400_000).toISOString().slice(0, 10),
            estimated_by: new Date(Date.now() + 42 * 86400_000).toISOString().slice(0, 10),
          };
          const confirmationDigest = createHash("sha256").update(`native-refund-confirmation:${email}`).digest("hex");
          const orderResult = await orderModule.createOrders({
            currency_code: "zar",
            email,
            status: "completed",
            items: [{
              title: "Synthetic native refund integration chair",
              quantity: 1,
              unit_price: 1150,
              is_tax_inclusive: true,
              requires_shipping: false,
            }],
            metadata: {
              storefront_fulfillment_promise: fulfillmentPromise,
              storefront_confirmation_sha256: confirmationDigest,
              storefront_checkout: { fulfillment_type: "collection" },
            },
          });
          const order = Array.isArray(orderResult) ? orderResult[0] : orderResult;
          if (!order || typeof order.id !== "string") throw new Error("medusa_native_test_order_create_failed");
          orderId = order.id;
          statusToken = customerStatusToken(orderId, confirmationDigest);
          captureId = randomUUID().replaceAll("-", "");
          const orderItem = Array.isArray(order.items) ? record(order.items[0]) : {};
          if (typeof orderItem?.id !== "string") throw new Error("medusa_native_test_order_line_create_failed");
          await orderModule.updateOrders([{
            id: orderId,
            metadata: {
              ...record(order.metadata),
              storefront_handoff_outbox: {
                status: "imported",
                payload: {
                  external_order_id: orderId,
                  currency_code: "ZAR",
                  totals: {
                    subtotal_ex_minor_zar: 100000,
                    tax_minor_zar: 15000,
                    delivery_ex_minor_zar: 0,
                    delivery_total_minor_zar: 0,
                    total_minor_zar: 115000,
                  },
                  payment: { amount_minor_zar: 115000, currency_code: "ZAR", captured_at: new Date().toISOString() },
                  lines: [{ external_line_id: orderItem.id, total_minor_zar: 115000 }],
                },
              },
            },
          }]);
          const collections = await createOrderPaymentCollectionWorkflow(container).run({
            input: { order_id: orderId, amount: 1150 },
          });
          const collection = collections.result[0];
          if (!collection?.id) throw new Error("medusa_native_test_payment_collection_create_failed");
          paymentCollectionId = String(collection.id);
          const session = await paymentModule.createPaymentSession_(collection.id, {
            provider_id: PEACH_PAYMENT_PROVIDER_ID,
            currency_code: "zar",
            amount: 1150,
            data: {},
          });
          if (typeof session.id !== "string") throw new Error("medusa_native_test_payment_session_create_failed");
          const attempt = await createPeachAttempt(db, {
            paymentSessionId: session.id,
            amountMinor: 115000,
            currencyCode: "ZAR",
          });
          await updatePeachAttempt(db, attempt.attempt.id, {
            checkout_id: "synthetic-captured-checkout",
            captured_transaction_id: captureId,
            captured_order_id: orderId,
            status: "captured",
            last_event_timestamp: new Date().toISOString(),
            last_event_state: "paid",
          });
          await paymentModule.updatePaymentSession({
            id: session.id,
            amount: 1150,
            currency_code: "zar",
            data: {
              peach_status: "paid",
              peach_merchant_reference: attempt.attempt.merchant_reference,
              peach_amount_minor: 115000,
              peach_checkout_id: "synthetic-captured-checkout",
              peach_transaction_id: captureId,
              currency_code: "ZAR",
            },
          });
          const payment = await paymentModule.authorizePaymentSession(session.id, {});
          if (!payment || typeof payment.id !== "string") throw new Error("medusa_native_test_capture_create_failed");
          paymentId = payment.id;
          await orderModule.addOrderTransactions([{
            order_id: orderId,
            amount: 1150,
            currency_code: "zar",
            reference: "capture",
            reference_id: captureId,
          }]);
          const orderQuery = container.resolve(ContainerRegistrationKeys.QUERY) as {
            graph(input: JsonRecord): Promise<{ data: JsonRecord[] }>;
          };
          const capturedOrder = await orderQuery.graph({
            entity: "order", fields: ["id", "total", "summary.raw_pending_difference"], filters: { id: orderId },
          });
          const capturedSnapshot = record(capturedOrder.data[0]);
          expect(medusaMajorAmount(record(capturedSnapshot.summary).raw_pending_difference)).toBe(0);
          expect(Number(capturedSnapshot.total)).toBe(1150);
          handoffId = await createFirstoutMtoHandoff(orderId, captureId);
        });

        afterAll(() => {
          globalThis.fetch = originalFetch;
        });

        test("converges partial, remaining, duplicate and interrupted local projection without another provider POST", async () => {
          const submitRefund = async (amountMinor: number): Promise<JsonRecord> => {
            return firstoutJson(`/api/v1/storefront/orders/${handoffId}/refunds`, {
              method: "POST",
              headers: {
                ...(await firstoutOwnerCookieHeaders()),
                "content-type": "application/json",
              },
              body: JSON.stringify({ idempotency_key: randomUUID(), amount_minor: amountMinor }),
				}, 200);
          };

          const runOneRefund = async (amountMinor: number) => {
            const request = await submitRefund(amountMinor);
            const result = await syncStorefrontPeachRefundCommands(container, simulator.fetcher);
            return { request, result };
          };

          const first = await runOneRefund(40000);
          expect(first.result.received).toBeGreaterThanOrEqual(1);
          expect(simulator.providerRequests).toHaveLength(1);
          const firstDispatch = await db("storefront_peach_refund_dispatch").where({ request_id: first.request.id }).first();
          expect(firstDispatch).toMatchObject({
            status: "succeeded",
            medusa_payment_id: paymentId,
            provider_refund_id: simulator.observations[0]?.provider_refund_id,
          });
          expect(Number(firstDispatch.amount_minor)).toBe(40000);

          const paymentModule = container.resolve(Modules.PAYMENT) as unknown as {
            retrievePayment(id: string, config: JsonRecord): Promise<JsonRecord>;
            retrievePaymentCollection(id: string, config: JsonRecord): Promise<JsonRecord>;
          };
          const orderModule = container.resolve(Modules.ORDER) as unknown as {
            listOrderTransactions(filters: JsonRecord, config: JsonRecord): Promise<JsonRecord[]>;
          };
          const query = container.resolve(ContainerRegistrationKeys.QUERY) as {
            graph(input: JsonRecord): Promise<{ data: JsonRecord[] }>;
          };
          const firstPayment = await paymentModule.retrievePayment(paymentId, { relations: ["captures", "refunds"] });
          expect(Number(firstPayment.amount)).toBe(1150);
          expect((firstPayment.captures as JsonRecord[]).reduce((sum, item) => sum + Number(item.amount), 0)).toBe(1150);
          expect((firstPayment.refunds as JsonRecord[])).toHaveLength(1);
          const firstCollection = await paymentModule.retrievePaymentCollection(paymentCollectionId, {});
          expect(Number(firstCollection.refunded_amount)).toBe(400);
          const firstCustomerStatus = record((await api.get(`/store/orders/${orderId}/storefront-status`, {
            headers: {
              "x-publishable-api-key": publishableApiKey,
              "x-storefront-bff-secret": testBffSecret,
              "x-storefront-order-status-token": statusToken,
            },
          })).data);
          const firstCustomerOrder = record(firstCustomerStatus.order);
          expect(Number(firstCustomerOrder.total)).toBe(1150);
          expect(firstCustomerOrder.captured_amount_minor).toBe(115000);
          expect(firstCustomerOrder.captured_at).toEqual(expect.any(String));
          expect(record(firstCustomerOrder.refund_status).refunded_amount_minor).toBe(40000);
          expect(Number(record((firstCustomerOrder.items as JsonRecord[])[0]).total)).toBe(1150);
          const firstRefundId = String((firstPayment.refunds as JsonRecord[])[0]?.id);
          const firstTransactions = await orderModule.listOrderTransactions({
            order_id: orderId, reference: "refund", reference_id: firstRefundId,
          }, { select: ["id", "amount", "currency_code", "reference", "reference_id"] });
          expect(firstTransactions).toHaveLength(1);
          expect(Number(firstTransactions[0]?.amount)).toBe(-400);
          let orderGraph = await query.graph({
            entity: "order",
            fields: ["id", "display_id", "metadata", "summary.raw_pending_difference", "summary.raw_refunded_total", "credit_lines.id", "credit_lines.amount", "credit_lines.reference", "credit_lines.reference_id"],
            filters: { id: orderId },
          });
          let orderSnapshot = record(orderGraph.data[0]);
          expect(medusaMajorAmount(record(orderSnapshot.summary).raw_refunded_total)).toBe(400);
          let metadata = record(orderSnapshot.metadata);
          let notificationOutbox = metadata.storefront_notification_outbox as JsonRecord[];
          expect(notificationOutbox.filter((entry) => entry.kind === "refund_status" && entry.status === "pending")).toHaveLength(1);
          let creditLines = orderSnapshot.credit_lines as JsonRecord[];
          expect(creditLines.filter((line) => line.reference === "storefront_refund" && line.reference_id === firstRefundId)).toHaveLength(1);
          expect(simulator.eventResponses[simulator.eventResponses.length - 1]).toMatchObject({
            status: "succeeded", provider_outcome: "succeeded", request_id: first.request.id,
          });
          expect(simulator.eventRequests[simulator.eventRequests.length - 1]).toMatchObject({
            event_source: "response", request_id: first.request.id, signature_verified: true,
          });

          const duplicateWebhook = eventFromObservation(simulator.observations[0]!, String(first.request.id));
          const firstDuplicateDelivery = await persistAndProcessRefundObservation(
            container,
            db,
            duplicateWebhook,
            "webhook",
            simulator.fetcher,
          );
          expect(firstDuplicateDelivery).toBe("processed");
          expect(simulator.eventResponses[simulator.eventResponses.length - 1]).toMatchObject({ duplicate: false, status: "succeeded" });
          const duplicate = await persistAndProcessRefundObservation(
            container,
            db,
            duplicateWebhook,
            "webhook",
            simulator.fetcher,
          );
          expect(duplicate).toBe("processed");
          expect(simulator.providerRequests).toHaveLength(1);
          expect(simulator.eventResponses[simulator.eventResponses.length - 1]).toMatchObject({ duplicate: true, status: "succeeded" });
          const duplicatePayment = await paymentModule.retrievePayment(paymentId, { relations: ["captures", "refunds"] });
          expect(duplicatePayment.refunds as JsonRecord[]).toHaveLength(1);
          const duplicateCollection = await paymentModule.retrievePaymentCollection(paymentCollectionId, {});
          expect(Number(duplicateCollection.refunded_amount)).toBe(400);

          // Seed older completed records to prove they cannot occupy the bounded
          // recovery query ahead of this order's interrupted projection.
          for (let index = 0; index < 30; index += 1) {
            const requestId = randomUUID();
            await db("storefront_peach_refund_dispatch").insert({
              id: `srefund_${requestId.replaceAll("-", "")}`,
              request_id: requestId,
              handoff_id: randomUUID(),
              external_order_id: `completed-test-row-${index}`,
              original_transaction_id: randomUUID().replaceAll("-", ""),
              amount_minor: 1,
              raw_amount_minor: { value: "1", precision: 20 },
              currency_code: "ZAR",
              cancel_order: false,
              allocation: {},
              status: "succeeded",
              firstout_status: "succeeded",
              provider_refund_id: randomUUID().replaceAll("-", ""),
              provider_result_code: "000.100.110",
              canonical_sha256: randomUUID().replaceAll("-", "").padEnd(64, "a"),
              medusa_payment_id: null,
              medusa_refund_id: null,
              authorization_key: null,
              deleted_at: null,
              created_at: new Date(Date.now() - (30 - index) * 60_000),
              updated_at: new Date(Date.now() - (30 - index) * 60_000),
            });
          }

          const functionName = `refund_projection_interrupt_${randomUUID().replaceAll("-", "")}`;
          const triggerName = `refund_projection_interrupt_${randomUUID().replaceAll("-", "")}`;
          await db.raw(`CREATE FUNCTION ${functionName}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.metadata IS DISTINCT FROM OLD.metadata AND NEW.metadata ? 'storefront_refunds' THEN RAISE EXCEPTION 'synthetic projection interruption'; END IF; RETURN NEW; END; $$`);
          await db.raw(`CREATE TRIGGER ${triggerName} BEFORE UPDATE OF metadata ON "order" FOR EACH ROW EXECUTE FUNCTION ${functionName}()`);
          const second = await submitRefund(75000);
          try {
            const interrupted = await syncStorefrontPeachRefundCommands(container, simulator.fetcher);
            expect(interrupted.received).toBeGreaterThanOrEqual(1);
            expect(simulator.providerRequests).toHaveLength(2);
            const localDuringInterruption = await db("storefront_peach_refund_dispatch").where({ request_id: second.id }).first();
            expect(localDuringInterruption?.status).toBe("recording_medusa_refund");
            expect(localDuringInterruption?.medusa_refund_id).toBeTruthy();
          } finally {
            await db.raw(`DROP TRIGGER IF EXISTS ${triggerName} ON "order"`);
            await db.raw(`DROP FUNCTION IF EXISTS ${functionName}()`);
          }

          const firstoutUnavailable: typeof fetch = async (input, init) => {
            const url = requestUrl(input);
            if (url.pathname.endsWith("/refund-commands")) return new Response("temporarily unavailable", { status: 503 });
            return simulator.fetcher(input, init);
          };
          const recovered = await syncStorefrontPeachRefundCommands(container, firstoutUnavailable);
          expect(recovered.received).toBe(0);
          expect(simulator.providerRequests).toHaveLength(2);
          const secondDispatch = await db("storefront_peach_refund_dispatch").where({ request_id: second.id }).first();
          expect(secondDispatch).toMatchObject({
            status: "succeeded",
            medusa_payment_id: paymentId,
            provider_refund_id: simulator.observations[1]?.provider_refund_id,
          });

          const finalPayment = await paymentModule.retrievePayment(paymentId, { relations: ["captures", "refunds"] });
          expect(finalPayment.refunds as JsonRecord[]).toHaveLength(2);
          const finalCollection = await paymentModule.retrievePaymentCollection(paymentCollectionId, {});
          expect(Number(finalCollection.refunded_amount)).toBe(1150);
          const finalCustomerStatus = record((await api.get(`/store/orders/${orderId}/storefront-status`, {
            headers: {
              "x-publishable-api-key": publishableApiKey,
              "x-storefront-bff-secret": testBffSecret,
              "x-storefront-order-status-token": statusToken,
            },
          })).data);
          const finalCustomerOrder = record(finalCustomerStatus.order);
          expect(Number(finalCustomerOrder.total)).toBe(1150);
          expect(finalCustomerOrder.captured_amount_minor).toBe(115000);
          expect(finalCustomerOrder.captured_at).toEqual(expect.any(String));
          expect(record(finalCustomerOrder.refund_status).refunded_amount_minor).toBe(115000);
          expect((record(finalCustomerOrder.refund_status).items as JsonRecord[]).map((item) => item.amount_minor)).toEqual([40000, 75000]);
          expect(Number(record((finalCustomerOrder.items as JsonRecord[])[0]).total)).toBe(1150);
          const secondRefundId = String((finalPayment.refunds as JsonRecord[]).find((refund) => refund.id !== firstRefundId)?.id);
          const secondTransactions = await orderModule.listOrderTransactions({
            order_id: orderId, reference: "refund", reference_id: secondRefundId,
          }, { select: ["id", "amount", "currency_code", "reference", "reference_id"] });
          expect(secondTransactions).toHaveLength(1);
          expect(Number(secondTransactions[0]?.amount)).toBe(-750);
          orderGraph = await query.graph({
            entity: "order",
            fields: ["id", "display_id", "metadata", "summary.raw_pending_difference", "summary.raw_refunded_total", "credit_lines.id", "credit_lines.amount", "credit_lines.reference", "credit_lines.reference_id"],
            filters: { id: orderId },
          });
          orderSnapshot = record(orderGraph.data[0]);
          expect(medusaMajorAmount(record(orderSnapshot.summary).raw_refunded_total)).toBe(1150);
          metadata = record(orderSnapshot.metadata);
          notificationOutbox = metadata.storefront_notification_outbox as JsonRecord[];
          creditLines = orderSnapshot.credit_lines as JsonRecord[];
          expect((metadata.storefront_refunds as JsonRecord[])).toHaveLength(2);
          expect(notificationOutbox.filter((entry) => entry.kind === "refund_status")).toHaveLength(2);
          expect(creditLines.filter((line) => line.reference === "storefront_refund")).toHaveLength(2);
          expect(simulator.eventRequests.filter((event) => event.event_source === "response")).toHaveLength(2);
          expect(simulator.eventResponses[simulator.eventResponses.length - 1]).toMatchObject({ status: "succeeded", provider_outcome: "succeeded" });

          const firstoutStatus = await firstoutJson(`/api/v1/storefront/orders/${handoffId}/refunds`, {
            method: "GET",
            headers: await firstoutOwnerCookieHeaders(),
          }, 200);
          const refundItems = firstoutStatus.items as JsonRecord[];
          expect(refundItems.filter((item) => item.status === "succeeded")).toHaveLength(2);
          expect(refundItems.every((item) => typeof item.financial_journal_id === "string")).toBe(true);
          expect(refundItems.reduce((sum, item) => sum + Number(item.amount_minor), 0)).toBe(115000);
        }, 180_000);
      });
    },
  });
} else {
  describe.skip("native Medusa refund convergence integration", () => {
    test("requires the disposable Medusa/Firstout integration environment", () => undefined);
  });
}

async function firstoutOwnerCookieHeaders(): Promise<Record<string, string>> {
  const base = process.env.STOREFRONT_FIRSTOUT_API_URL!.replace(/\/+$/, "");
  const response = await originalFetch(`${base}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: process.env.FIRSTOUT_OWNER_EMAIL, password: process.env.FIRSTOUT_OWNER_PASSWORD }),
  });
  if (!response.ok) throw new Error(`firstout_login_http_${response.status}`);
  const cookie = response.headers.get("set-cookie")?.match(/firstout_session=[^;]+/)?.[0];
  if (!cookie) throw new Error("firstout_owner_session_cookie_missing");
  return { cookie };
}
