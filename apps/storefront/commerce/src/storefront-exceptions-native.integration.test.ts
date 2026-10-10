import { randomUUID } from "node:crypto";
import path from "node:path";
import type { Knex } from "knex";
import { medusaIntegrationTestRunner } from "@medusajs/test-utils";
import { createOrderPaymentCollectionWorkflow } from "@medusajs/medusa/core-flows";
import type { IInventoryService, IOrderModuleService, IPaymentModuleService, IProductModuleService, IStockLocationService, MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { collectStorefrontExceptionSources, type ExceptionScan } from "./storefront-exception-sources";
import { syncStorefrontExceptions, type ExceptionCommand } from "./storefront-exception-worker";
import { recordOpsCheckoutHealth } from "./storefront-commerce-exceptions";
import exceptionJob from "./jobs/sync-storefront-exceptions";
import { createPeachAttempt, createPeachRefundDispatch, PEACH_ATTEMPTS_TABLE, updatePeachAttempt } from "./peach-payment-store";
import { ensureStorefrontOrderOutbox } from "./storefront-order-handoff";
import { Migration20260930180331 } from "./modules/storefront-peach/migrations/Migration20260930180331";
import { Migration20261001090000 } from "./modules/storefront-peach/migrations/Migration20261001090000";
import { Migration20261009120000 } from "./modules/storefront-peach/migrations/Migration20261009120000";

jest.setTimeout(180000);
const enabled = process.env.STOREFRONT_NATIVE_EXCEPTIONS_LIVE_TEST === "1";
if (enabled) {
  const loopback = ["localhost", "127.0.0.1", "[::1]"];
  if (!process.env.DATABASE_URL || !process.env.REDIS_URL || !process.env.DB_HOST ||
      !loopback.includes(new URL(process.env.DATABASE_URL).hostname) || !loopback.includes(new URL(process.env.REDIS_URL).hostname) || !loopback.includes(process.env.DB_HOST)) {
    throw new Error("Native exception tests require isolated local database and Redis");
  }
  const appPath = path.resolve(__dirname, "..");
  medusaIntegrationTestRunner({ moduleName: `exceptions-${randomUUID().slice(0, 8)}`, cwd: appPath, medusaConfigFile: appPath,
    env: { NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test", STOREFRONT_TEST_PAYMENT_ENABLED: "true",
      FIRSTOUT_OPS_URL: "https://firstout.invalid/ops-commerce/v1", FIRSTOUT_OPS_TOKEN: "isolated-fixture-token", FIRSTOUT_OPS_COMPANY_ID: "test-company",
    }, testSuite: ({ getContainer }) => {
      let container: MedusaContainer;
      let db: Knex;
      let inventory: IInventoryService;
      let orders: IOrderModuleService;
      let orderId: string;
      let variantId: string;
      let expiredId: string;
      let activeHoldId: string;
      let paidReservationId: string;
      let unknownId: string;
      let capturedId: string;
      const scans: ExceptionScan[] = [];
      const calls: string[] = [];
      let pending: ExceptionCommand[] = [];
      let feedFailure = false;
      let imported = false;
      const results: { outcome: string; detail: string }[] = [];
      const originalFetch = globalThis.fetch;
      const boundary: typeof fetch = async (input, init) => {
        const url = String(input);
        calls.push(`${init?.method || "GET"} ${url}`);
        if (!url.startsWith("https://firstout.invalid/")) throw new Error("native_exception_fixture_blocks_provider_transport");
        if (url.includes("/fulfillment-events?")) return new Response(JSON.stringify({ items: [{ occurred_at: new Date(Date.now() - 1000).toISOString() }] }), { status: feedFailure ? 503 : 200 });
        if (url.endsWith("/exceptions/observations")) {
          scans.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify({ accepted: true, checkout_allowed: true }));
        }
        if (url.endsWith("/exceptions/commands")) return new Response(JSON.stringify({ items: pending }));
        if (url.endsWith("/result")) {
          results.push(JSON.parse(String(init?.body)));
          return new Response(JSON.stringify({ outcome: results.at(-1)?.outcome }));
        }
        if (url.endsWith("/orders/status")) {
          const ids: string[] = JSON.parse(String(init?.body)).external_order_ids;
          return new Response(JSON.stringify({ items: ids.map((id) => ({ external_order_id: id, status: imported ? "imported" : "missing" })) }));
        }
        if (url.endsWith("/orders") && init?.method === "POST") {
          const payload = JSON.parse(String(init.body));
          expect(payload.external_order_id).toBe(orderId);
          expect(payload.payment.amount_minor_zar).toBe(10000);
          imported = true;
          return new Response(JSON.stringify({ status: "imported" }), { status: 201 });
        }
        throw new Error("unexpected_exception_fixture_endpoint");
      };
      const command = (kind: ExceptionCommand["kind"], id: string, action: string): ExceptionCommand => ({
        id: randomUUID(), kind, action, correlation_id: `storefront:${kind}:${id}`, idempotency_key: randomUUID(),
      });
      beforeAll(async () => {
        container = getContainer(); db = container.resolve(ContainerRegistrationKeys.PG_CONNECTION);
        inventory = container.resolve(Modules.INVENTORY); orders = container.resolve(Modules.ORDER);
        globalThis.fetch = boundary;
        const sql: string[] = [];
        for (const Type of [Migration20260930180331, Migration20261001090000, Migration20261009120000]) {
          const migration = Object.create(Type.prototype);
          Reflect.set(migration, "addSql", (statement: string) => sql.push(statement));
          await migration.up();
        }
        for (const statement of sql) await db.raw(statement);
        const products = container.resolve<IProductModuleService>(Modules.PRODUCT);
        const sourceSku = randomUUID();
        const product = await products.createProducts({ title: "Exception fixture", status: "published", options: [{ title: "Item", values: ["Standard"] }], variants: [{
          title: "Standard", sku: `EX-${randomUUID()}`, manage_inventory: true, options: { Item: "Standard" },
          metadata: { source_sku_id: sourceSku, source_observed_at: new Date(Date.now() - 600000).toISOString() },
        }] });
        const variant = product.variants![0]; variantId = variant.id;
        // Retired projections must not create a permanent checkout block.
        const retired = await products.createProducts({ title: "Retired fixture", status: "draft", options: [{ title: "Item", values: ["Retired", ...Array.from({ length: 500 }, (_, index) => `Retired-${index}`)] }], variants: [{ title: "Retired", options: { Item: "Retired" }, metadata: { source_sku_id: randomUUID(), source_observed_at: "2020-01-01T00:00:00Z" } }] });
        await products.createProductVariants(Array.from({ length: 500 }, (_, index) => ({ product_id: retired.id,
          title: `Retired page ${index}`, sku: `RET-${randomUUID()}`, options: { Item: `Retired-${index}` }, manage_inventory: false,
          metadata: { source_sku_id: randomUUID(), source_observed_at: "2020-01-01T00:00:00Z" },
        })));
        const location = await container.resolve<IStockLocationService>(Modules.STOCK_LOCATION).createStockLocations({ name: "Exception stock fixture" });
        const item = await inventory.createInventoryItems({ sku: `EX-INV-${randomUUID()}` });
        await inventory.createInventoryLevels({ inventory_item_id: item.id, location_id: location.id, stocked_quantity: 10 });
        await container.resolve(ContainerRegistrationKeys.LINK).create({ [Modules.PRODUCT]: { variant_id: variant.id }, [Modules.INVENTORY]: { inventory_item_id: item.id } });
        expiredId = (await inventory.createReservationItems({ inventory_item_id: item.id, location_id: location.id, quantity: 1,
          created_by: "storefront_hold:expired", metadata: { expires_at: new Date(Date.now() - 60000).toISOString() } })).id;
        activeHoldId = (await inventory.createReservationItems({ inventory_item_id: item.id, location_id: location.id, quantity: 1,
          created_by: "storefront_hold:active", metadata: { expires_at: new Date(Date.now() + 600000).toISOString() } })).id;
        const order = await orders.createOrders({ currency_code: "zar", email: "native-exception@example.test", status: "completed",
          shipping_address: { first_name: "Native", last_name: "Buyer", address_1: "1 Test Street", city: "Cape Town", country_code: "za", province: "Western Cape", postal_code: "8001", phone: "+27123456789" },
          metadata: { storefront_confirmation_sha256: "b".repeat(64), storefront_checkout: { fulfillment_type: "collection" },
            storefront_capacity_exception: { status: "paid_exception", recorded_at: new Date().toISOString() } },
          items: [{ title: "Exception fixture", quantity: 1, unit_price: 100, variant_id: variant.id }] });
        orderId = order.id;
        const { result: collections } = await createOrderPaymentCollectionWorkflow(container).run({ input: { order_id: order.id, amount: 100 } });
        const payments = container.resolve<IPaymentModuleService>(Modules.PAYMENT);
        const session = await payments.createPaymentSession(collections[0].id, { provider_id: "pp_storefront-test_local", currency_code: "zar", amount: 100, data: {} });
        const payment = await payments.authorizePaymentSession(session.id, {});
        if (!payment) throw new Error("Native fixture authorization failed");
        await payments.capturePayment({ payment_id: payment.id });
        paidReservationId = (await inventory.createReservationItems({ inventory_item_id: item.id, location_id: location.id, line_item_id: order.items![0].id, quantity: 1 })).id;
        const outbox = await ensureStorefrontOrderOutbox(container, order.id);
        expect(outbox?.payload).toBeTruthy();
        await orders.updateOrders([{ id: order.id, metadata: { ...order.metadata, storefront_handoff_outbox: { ...outbox, status: "failed", failure_code: "ops_rejected_handoff" } } }]);
        const unknown = await createPeachAttempt(db, { paymentSessionId: "unknown-session", amountMinor: 1200, currencyCode: "ZAR" });
        unknownId = unknown.attempt.id;
        await updatePeachAttempt(db, unknownId, { status: "unknown" });
        const stored = await db(PEACH_ATTEMPTS_TABLE).where({ id: unknownId }).first();
        await db(PEACH_ATTEMPTS_TABLE).insert(Array.from({ length: 500 }, (_, i) => ({ ...stored,
          id: `spay_paged_${String(i).padStart(4, "0")}`, payment_session_id: `paged_session_${i}`, merchant_reference: `paged_reference_${i}`, nonce: `paged_nonce_${i}` })));
        const captured = await createPeachAttempt(db, { paymentSessionId: "deleted-native-session", cartId: "deleted-cart", checkoutSnapshot: { retained: true }, amountMinor: 999, currencyCode: "ZAR" });
        capturedId = captured.attempt.id;
        await updatePeachAttempt(db, capturedId, { status: "captured", captured_transaction_id: "verified-provider-charge" });
        const refund = await createPeachRefundDispatch(db, { request_id: "unknown-refund", handoff_id: "handoff", external_order_id: orderId,
          original_transaction_id: "original-capture", amount_minor: 500, currency_code: "ZAR", cancel_order: false, status: "authorized" });
        await db("storefront_peach_refund_dispatch").where({ id: refund.dispatch.id }).update({ status: "unknown" });
      });
      afterAll(() => { globalThis.fetch = originalFetch; });
      beforeEach(() => { scans.length = 0; calls.length = 0; results.length = 0; pending = []; feedFailure = false; });
      test("observes all seven real condition kinds and every durable unknown row while disabled Peach money remains visible", async () => {
        const scan = await collectStorefrontExceptionSources(container, boundary);
        expect(new Set(scan.observations.map((row) => row.kind))).toEqual(new Set(["aged_hold", "stale_sync", "missing_operational_paid_order", "unknown_payment", "refund_mismatch", "fulfilment_drift", "capacity_conflict"]));
        expect(scan.observations.filter((row) => row.kind === "unknown_payment")).toHaveLength(501);
        expect(scan.observations.find((row) => row.correlation_id.endsWith(capturedId))).toMatchObject({ amount_minor: 999, provider_verified: true, blocks_checkout: true });
      });
      test("staff hold repair actually releases expired native reservations before publishing convergence and keeps other reservations", async () => {
        pending = [command("aged_hold", expiredId, "release_expired_hold")];
        await syncStorefrontExceptions(container, boundary);
        expect(scans[0].observations.some((row) => row.correlation_id.endsWith(expiredId))).toBe(true);
        expect(scans[1].observations.some((row) => row.correlation_id.endsWith(expiredId))).toBe(false);
        expect(results).toEqual([{ outcome: "repaired", detail: "fresh_complete_scan_confirms_source_convergence" }]);
        const remaining = await inventory.listReservationItems({ id: [activeHoldId, paidReservationId] });
        expect(remaining).toHaveLength(2);
        expect(calls.at(-2)).toContain("/exceptions/observations");
        expect(calls.at(-1)).toContain("/result");
        const products = container.resolve<IProductModuleService>(Modules.PRODUCT);
        const active = await products.retrieveProductVariant(variantId);
        await products.updateProductVariants(variantId, { metadata: { ...active.metadata, source_observed_at: new Date().toISOString(),
          storefront_made_to_order_capacity: { version: 1, current_offer_id: "exhausted", allocations: { exhausted: {
            id: "exhausted", capacity: 0, min_lead_time_days: 1, max_lead_time_days: 2, expires_at: "2020-01-01T00:00:00Z", source_revision: "expired", holds: {}, committed: {},
          } } },
        } });
        const refreshed = await collectStorefrontExceptionSources(container, boundary);
        expect(refreshed.observations.some((row) => row.kind === "stale_sync")).toBe(false);
        expect(refreshed.observations.filter((row) => row.kind === "capacity_conflict")).toHaveLength(1); // Only the paid order, not exhausted offers.
        recordOpsCheckoutHealth({ opsReachable: false, lastProjectionAt: new Date(Date.now() - 1000).toISOString() });
        expect((await collectStorefrontExceptionSources(container, boundary)).observations.some((row) => row.kind === "stale_sync")).toBe(true);
        recordOpsCheckoutHealth({ opsReachable: true });
      });
      test("native paid-order repair performs an operational POST and capacity preparation before clearing its source condition", async () => {
        pending = [command("missing_operational_paid_order", orderId, "retry_handoff")];
        await syncStorefrontExceptions(container, boundary);
        expect(calls.some((call) => call.endsWith("POST https://firstout.invalid/ops-commerce/v1/orders"))).toBe(true);
        expect(results[0].outcome).toBe("repaired");
        const stored = await orders.retrieveOrder(orderId);
        expect(stored.metadata?.storefront_handoff_outbox).toMatchObject({ status: "imported" });
        expect(stored.metadata?.storefront_capacity_exception).toMatchObject({ status: "resolved" });
        await syncStorefrontExceptions(container, boundary);
        expect(calls.filter((call) => call.endsWith("POST https://firstout.invalid/ops-commerce/v1/orders"))).toHaveLength(1);
        imported = false; // Ops restore lost the receipt/SO while native outbox still says imported.
        const restoredScan = await collectStorefrontExceptionSources(container, boundary);
        expect(restoredScan.observations.some((row) => row.correlation_id === `storefront:missing_operational_paid_order:${orderId}`)).toBe(true);
        await syncStorefrontExceptions(container, boundary);
        expect(imported).toBe(true);
        expect(calls.filter((call) => call.endsWith("POST https://firstout.invalid/ops-commerce/v1/orders"))).toHaveLength(2);
      });
      test("unverified money and unsupported missing-order recovery remain actionable, and source-read failures never publish a scan", async () => {
        pending = [command("unknown_payment", unknownId, "verify_with_provider"), command("missing_operational_paid_order", capturedId, "retry_handoff"), command("refund_mismatch", "unknown-refund", "reproject_verified_refund")];
        await syncStorefrontExceptions(container, boundary);
        expect(results.map((row) => row.outcome)).toEqual(["not_repaired", "not_repaired", "not_repaired"]);
        expect(calls.every((call) => !call.includes("peachpayments.com"))).toBe(true);
        scans.length = 0; calls.length = 0;
        feedFailure = true;
        await expect(syncStorefrontExceptions(container, boundary)).rejects.toThrow("exception_fulfillment_feed_http_503");
        expect(scans).toHaveLength(0);
        expect(calls.some((call) => call.endsWith("/result"))).toBe(false);
        await exceptionJob(container); // NODE_ENV=test never publishes against inherited credentials.
        expect(scans).toHaveLength(0);
      });
    },
  });
} else {
  describe.skip("native exceptions integration requires explicit isolated local services", () => {
    test("opt in with STOREFRONT_NATIVE_EXCEPTIONS_LIVE_TEST=1", () => undefined);
  });
}
