import knexFactory, { type Knex } from "knex";
import { randomUUID } from "node:crypto";
import { ContainerRegistrationKeys, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { AuthorizePaymentInput, CapturePaymentInput, MedusaContainer, ProviderWebhookPayload } from "@medusajs/framework/types";
import {
  claimPeachRefundDispatchForDispatch, claimPeachRefundForMedusa, claimPeachWebhook, completePeachWebhook,
  createPeachAttempt, createPeachRefundDispatch, findPeachAttemptByReference, findPeachRefundDispatch,
  peachEventCanAdvance, receivePeachWebhook, updatePeachAttempt, updatePeachRefundDispatch,
} from "./peach-payment-store";
import { processClaimedPeachWebhook } from "./peach-webhook-processing";
import { parsePeachWebhook } from "./peach-checkout";
import { StorefrontPeachPaymentProvider } from "./modules/storefront-peach-payment-provider/service";
import { Migration20260930180331 } from "./modules/storefront-peach/migrations/Migration20260930180331";
import { Migration20261001090000 } from "./modules/storefront-peach/migrations/Migration20261001090000";
import { Migration20261009120000 } from "./modules/storefront-peach/migrations/Migration20261009120000";
import processPeachWebhooksJob from "./jobs/process-peach-webhooks";
import {
  persistAndProcessRefundObservation, processClaimedPeachRefundWebhook, syncStorefrontPeachRefundCommands,
} from "./storefront-peach-refunds";

const databaseUrl = process.env.STOREFRONT_PG_TEST_URL;
const describeWithPostgres = databaseUrl ? describe : describe.skip;

function webhook(webhookId: string, merchantReference: string, timestamp: string, resultCode: string, amount = "10.00") {
  const body = new URLSearchParams({
    amount, checkoutId: "checkout-1", currency: "ZAR", id: "txn-1",
    merchantTransactionId: merchantReference, paymentType: "DB", result_code: resultCode, timestamp,
  }).toString();
  const event = parsePeachWebhook(body, webhookId);
  if (!event) throw new Error("Test webhook fixture is invalid");
  return event;
}

describeWithPostgres("Peach durable inbox (isolated PostgreSQL)", () => {
  let admin: Knex;
  let db: Knex;
  let schema: string;
  const originalOpsEnv = {
    url: process.env.FIRSTOUT_OPS_URL,
    token: process.env.FIRSTOUT_OPS_TOKEN,
    companyId: process.env.FIRSTOUT_OPS_COMPANY_ID,
  };
  const peachEnvKeys = [
    "PEACH_ENVIRONMENT", "PEACH_CLIENT_ID", "PEACH_CLIENT_SECRET", "PEACH_MERCHANT_ID",
    "PEACH_ENTITY_ID", "PEACH_WEBHOOK_SECRET", "PEACH_CHECKOUT_SECRET", "PEACH_WEBHOOK_URL",
    "STOREFRONT_PUBLIC_URL",
  ] as const;
  const originalPeachEnv = Object.fromEntries(peachEnvKeys.map((key) => [key, process.env[key]]));

  beforeAll(async () => {
    process.env.FIRSTOUT_OPS_URL = "https://firstout.invalid/api/v1/ops-commerce/v1";
    process.env.FIRSTOUT_OPS_TOKEN = "disposable-test-token";
    process.env.FIRSTOUT_OPS_COMPANY_ID = "disposable-test-company";
    Object.assign(process.env, {
      PEACH_ENVIRONMENT: "sandbox",
      PEACH_CLIENT_ID: "disposable-client",
      PEACH_CLIENT_SECRET: "disposable-client-secret",
      PEACH_MERCHANT_ID: "disposable-merchant",
      PEACH_ENTITY_ID: "disposable-entity",
      PEACH_WEBHOOK_SECRET: "disposable-webhook-secret",
      PEACH_CHECKOUT_SECRET: "disposable-checkout-secret",
      PEACH_WEBHOOK_URL: "http://localhost:9000/hooks/peach",
      STOREFRONT_PUBLIC_URL: "http://localhost:3004",
    });
    admin = knexFactory({ client: "pg", connection: databaseUrl });
    schema = `peach_test_${randomUUID().replaceAll("-", "")}`;
    await admin.raw("CREATE SCHEMA ??", [schema]);
    db = knexFactory({ client: "pg", connection: databaseUrl, searchPath: [schema] });
    const migrationSql: string[] = [];
    const migrationCollector: Migration20260930180331 = Object.create(Migration20260930180331.prototype);
    Reflect.set(migrationCollector, "addSql", (statement: string) => migrationSql.push(statement));
    await migrationCollector.up();
    const refundMigrationCollector: Migration20261001090000 = Object.create(Migration20261001090000.prototype);
    Reflect.set(refundMigrationCollector, "addSql", (statement: string) => migrationSql.push(statement));
    await refundMigrationCollector.up();
    const bindingMigrationCollector: Migration20261009120000 = Object.create(Migration20261009120000.prototype);
    Reflect.set(bindingMigrationCollector, "addSql", (statement: string) => migrationSql.push(statement));
    await bindingMigrationCollector.up();
    for (const statement of migrationSql) await db.raw(statement);
  });

  afterAll(async () => {
    if (db) await db.destroy();
    if (admin && schema) {
      await admin.raw("DROP SCHEMA ?? CASCADE", [schema]);
      await admin.destroy();
    }
    if (originalOpsEnv.url === undefined) delete process.env.FIRSTOUT_OPS_URL;
    else process.env.FIRSTOUT_OPS_URL = originalOpsEnv.url;
    if (originalOpsEnv.token === undefined) delete process.env.FIRSTOUT_OPS_TOKEN;
    else process.env.FIRSTOUT_OPS_TOKEN = originalOpsEnv.token;
    if (originalOpsEnv.companyId === undefined) delete process.env.FIRSTOUT_OPS_COMPANY_ID;
    else process.env.FIRSTOUT_OPS_COMPANY_ID = originalOpsEnv.companyId;
    for (const key of peachEnvKeys) {
      const value = originalPeachEnv[key];
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });

  test("persists original checkout context before hosted POST and keeps a deleted-session capture in the real inbox", async () => {
    const sessionId = `session-deleted-${randomUUID()}`;
    const cartId = `cart-original-${randomUUID()}`;
    const snapshot = { id: cartId, total: 10, currency_code: "zar", items: [{ id: "item_original", quantity: 1 }] };
    const provider = new StorefrontPeachPaymentProvider({ [ContainerRegistrationKeys.PG_CONNECTION]: db });
    const hostedBoundary = jest.spyOn(global, "fetch").mockImplementation(async (url) => {
      if (String(url).endsWith("/api/oauth/token")) {
        return new Response(JSON.stringify({ access_token: "test-provider-token", expires_in: 300 }), { status: 200 });
      }
      expect(String(url)).toMatch(/\/v2\/checkout$/);
      // This assertion runs at the external boundary, before Peach could accept
      // money and before its response has supplied a checkout ID.
      const durable = await db("storefront_peach_payment_attempt").where({ payment_session_id: sessionId }).first();
      expect(durable).toMatchObject({ cart_id: cartId, checkout_snapshot: snapshot, status: "initiating" });
      return new Response(JSON.stringify({ checkoutId: "checkout-1", redirectUrl: "https://testsecure.peachpayments.com/pay/test" }), { status: 200 });
    });
    try {
      await provider.initiatePayment({ amount: 10, currency_code: "zar", context: { idempotency_key: sessionId },
        data: { storefront_cart_id: cartId, storefront_checkout_snapshot: snapshot } });
    } finally {
      hostedBoundary.mockRestore();
    }
    const attempt = await db("storefront_peach_payment_attempt").where({ payment_session_id: sessionId }).first();
    const event = webhook(`deleted-paid-${randomUUID()}`, attempt.merchant_reference, new Date().toISOString(), "000.000.000");
    const inbox = await receivePeachWebhook(db, event, "verified-test-signature");
    const claimed = await claimPeachWebhook(db, inbox.id);
    if (!claimed) throw new Error("Paid inbox row was not claimable");
    // Query and locking are the native Medusa adapters. All attempt/inbox
    // persistence, event advancement and the inventory-lock wrapper are real.
    const locking = { execute: async (_key: string, operation: () => Promise<unknown>) => operation() };
    const graph = async ({ entity }: { entity: string }) => {
      if (entity === "payment_session" || entity === "cart") return { data: [] };
      throw new Error(`Unexpected graph entity ${entity}`);
    };
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    expect(await processClaimedPeachWebhook(container, db, claimed)).toBe("paid_exception");
    expect(await findPeachAttemptByReference(db, attempt.merchant_reference)).toMatchObject({
      cart_id: cartId, checkout_snapshot: snapshot, status: "captured", captured_transaction_id: event.transaction_id,
      last_event_state: "paid",
    });
    expect(await db("storefront_peach_webhook_inbox").where({ id: claimed.id }).first()).toMatchObject({
      status: "paid_exception", lease_token: null, transaction_id: event.transaction_id,
    });
    expect(await claimPeachWebhook(db, inbox.id)).toBeUndefined();
    await db("storefront_peach_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("deduplicates by webhook ID and atomically permits one concurrent claim", async () => {
    const event = webhook(`dedupe-${randomUUID()}`, "TestReference01", new Date().toISOString(), "000.200.000");
    const first = await receivePeachWebhook(db, event, "signature-a");
    const replay = await receivePeachWebhook(db, event, "signature-b");
    expect(replay).toEqual({ id: first.id, duplicate: true });
    await expect(receivePeachWebhook(db, { ...event, result_code: "800.100.153", canonical_sha256: "different" }, "signature-a"))
      .rejects.toThrow(/different payment data/i);
    await expect(receivePeachWebhook(db, { ...event, canonical_sha256: "status-observation-with-same-provider-id" }, null, "status"))
      .rejects.toMatchObject({ code: "23505" });

    const claims = await Promise.all([claimPeachWebhook(db, first.id), claimPeachWebhook(db, first.id)]);
    expect(claims.filter(Boolean)).toHaveLength(1);
    const claimed = claims.find(Boolean)!;
    expect(claimed.lease_token).toMatch(/^[a-f\d-]{36}$/i);

    // A DB timestamp with microseconds cannot round-trip through JS Date, so
    // completion must fence on the opaque token rather than lease_until.
    await db("storefront_peach_webhook_inbox").where({ id: claimed.id }).update({
      lease_until: db.raw("'2026-09-30T12:00:00.123456Z'::timestamptz"),
    });
    await completePeachWebhook(db, claimed.id, claimed.lease_token, "processed");
    expect(await claimPeachWebhook(db, first.id)).toBeUndefined();
  });

  test("uses the active partial index for idempotency and preserves exact minor amounts above int32", async () => {
    const event = webhook(`soft-delete-${randomUUID()}`, "TestReference01", new Date().toISOString(), "000.200.000");
    const first = await receivePeachWebhook(db, event, "signature-a");
    await db("storefront_peach_webhook_inbox").where({ id: first.id }).update({ deleted_at: new Date() });
    const replacement = await receivePeachWebhook(db, event, "signature-b");
    expect(replacement.duplicate).toBe(false);
    expect(replacement.id).not.toBe(first.id);

    const amountMinor = 4_000_000_000;
    const attempt = await createPeachAttempt(db, {
      paymentSessionId: `large-session-${randomUUID()}`, amountMinor, currencyCode: "ZAR",
    });
    const largeEvent = webhook(`large-${randomUUID()}`, attempt.attempt.merchant_reference,
      new Date().toISOString(), "000.200.000", "40000000.00");
    const inbox = await receivePeachWebhook(db, largeEvent, "signature-large");
    const storedAttempt = await db("storefront_peach_payment_attempt").where({ id: attempt.attempt.id }).first();
    const storedEvent = await db("storefront_peach_webhook_inbox").where({ id: inbox.id }).first();
    expect(Number(storedAttempt.amount_minor)).toBe(amountMinor);
    expect(storedAttempt.raw_amount_minor).toEqual({ value: String(amountMinor), precision: 20 });
    expect(Number(storedEvent.amount_minor)).toBe(amountMinor);
    expect(storedEvent.raw_amount_minor).toEqual({ value: String(amountMinor), precision: 20 });
  });

  test("concurrent refund command creation converges on one immutable dispatch and one provider claim", async () => {
    const requestId = randomUUID();
    const command = {
      request_id: requestId,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: "8ac7a4a284c684140184c7a8f19a5530",
      amount_minor: 1250,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 750, line_b: 500 },
      status: "requested",
    };
      const created = await Promise.all([
      createPeachRefundDispatch(db, command),
      createPeachRefundDispatch(db, command),
    ]);
    expect(new Set(created.map((value) => value.dispatch.id)).size).toBe(1);
    expect(created.filter((value) => value.created)).toHaveLength(1);
    expect(created.map((value) => value.created).sort()).toEqual([false, true]);
    await expect(createPeachRefundDispatch(db, { ...command, allocation: { line_a: 749, line_b: 501 } }))
      .rejects.toThrow(/changed after it was durably received/i);

    const claims = await Promise.all([
      claimPeachRefundDispatchForDispatch(db, requestId),
      claimPeachRefundDispatchForDispatch(db, requestId),
    ]);
    expect(claims.filter(Boolean)).toHaveLength(1);
    expect((await findPeachRefundDispatch(db, requestId))?.status).toBe("dispatching");
    expect(await claimPeachRefundDispatchForDispatch(db, requestId)).toBe(false);
  });

  test("native Medusa refund capability can be consumed only by the matching verified intent", async () => {
    const requestId = randomUUID();
    const command = {
      request_id: requestId,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: "8ac7a4a284c684140184c7a8f19a5530",
      amount_minor: 500,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 500 },
      status: "requested",
    };
    await createPeachRefundDispatch(db, command);
    const providerRefundId = "8ac7a49f8af08e94018af09246760e30";
    const capability = randomUUID();
    await db("storefront_peach_refund_dispatch").where({ request_id: requestId }).update({
      status: "verified", provider_refund_id: providerRefundId, authorization_key: capability,
    });
    const input = {
      requestId, providerRefundId, capability, paymentId: `pay_${randomUUID()}`,
      refundId: `ref_${randomUUID()}`, amountMinor: 500,
    };
    await updatePeachRefundDispatch(db, requestId, { medusa_payment_id: `pay_${randomUUID()}` });
    const boundPaymentId = (await findPeachRefundDispatch(db, requestId))?.medusa_payment_id;
    expect(await claimPeachRefundForMedusa(db, input)).toBe(false);
    expect(await findPeachRefundDispatch(db, requestId)).toMatchObject({
      status: "verified", medusa_payment_id: boundPaymentId, medusa_refund_id: null,
    });
    input.paymentId = boundPaymentId!;
    expect(await claimPeachRefundForMedusa(db, input)).toBe(true);
    expect(await claimPeachRefundForMedusa(db, input)).toBe(true);
    expect(await claimPeachRefundForMedusa(db, { ...input, refundId: `ref_${randomUUID()}` })).toBe(false);
    expect((await findPeachRefundDispatch(db, requestId))?.status).toBe("recording_medusa_refund");
  });

  test("recovers remote dispatching commands as unknown without ever resending Peach RF", async () => {
    const commands = [
      { localStatus: "dispatching", request_id: randomUUID() },
      { localStatus: "received", request_id: randomUUID() },
    ].map((item) => ({
      request_id: item.request_id,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: randomUUID().replaceAll("-", "").slice(0, 32),
      amount_minor: 1250,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 1250 },
      status: "dispatching",
      local_status: item.localStatus,
    }));
    for (const command of commands) {
      await createPeachRefundDispatch(db, command);
      await updatePeachRefundDispatch(db, command.request_id, { status: command.local_status });
    }
    const outcomeBodies: Record<string, unknown>[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("refund-commands?limit=100")) {
        return new Response(JSON.stringify({ items: commands.map(({ local_status: _local, ...command }) => command) }), {
          status: 200, headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/refund-commands/") && url.endsWith("/outcome")) {
        const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        outcomeBodies.push(body);
        return new Response(JSON.stringify({ status: "unknown" }), {
          status: 200, headers: { "content-type": "application/json" },
        });
      }
      throw new Error("Unexpected external request in dispatch recovery test");
    });
    const locking = { execute: async (_key: string, operation: () => Promise<unknown>) => operation() };
    const container = {
      resolve(key: string) {
        if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
        if (key === Modules.LOCKING) return locking;
        throw new Error(`Unexpected Medusa service ${key}`);
      },
    } as unknown as MedusaContainer;

    await expect(syncStorefrontPeachRefundCommands(container, fetcher as typeof fetch))
      .resolves.toEqual({ received: commands.length, dispatched: commands.length });
    expect(fetcher).toHaveBeenCalledTimes(1 + commands.length);
    expect(fetcher.mock.calls.map(([input]) => String(input)).some((url) => url.includes("testapi.peachpayments.com"))).toBe(false);
    expect(outcomeBodies).toHaveLength(commands.length);
    expect(outcomeBodies.every((body) => body.status === "unknown")).toBe(true);
    for (const command of commands) {
      expect(await findPeachRefundDispatch(db, command.request_id)).toMatchObject({
        status: "unknown", provider_refund_id: null, provider_result_code: null,
      });
    }
  });

  test("does not downgrade a completed local refund from a stale remote dispatching snapshot", async () => {
    const requestId = randomUUID();
    const command = {
      request_id: requestId,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: randomUUID().replaceAll("-", "").slice(0, 32),
      amount_minor: 1250,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 1250 },
      status: "dispatching",
    };
    await createPeachRefundDispatch(db, command);
    await updatePeachRefundDispatch(db, requestId, {
      status: "succeeded",
      firstout_status: "succeeded",
      provider_refund_id: randomUUID().replaceAll("-", ""),
      provider_result_code: "000.200.000",
      canonical_sha256: "a".repeat(64),
      medusa_payment_id: null,
      medusa_refund_id: "ref_locally_completed",
    });
    const before = await findPeachRefundDispatch(db, requestId);
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ items: [command] }), {
      status: 200, headers: { "content-type": "application/json" },
    }));
    const locking = { execute: async (_key: string, operation: () => Promise<unknown>) => operation() };
    const container = {
      resolve(key: string) {
        if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
        if (key === Modules.LOCKING) return locking;
        throw new Error(`Unexpected Medusa service ${key}`);
      },
    } as unknown as MedusaContainer;

    await expect(syncStorefrontPeachRefundCommands(container, fetcher as typeof fetch))
      .resolves.toEqual({ received: 1, dispatched: 1 });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(await findPeachRefundDispatch(db, requestId)).toMatchObject({
      status: "succeeded",
      firstout_status: "succeeded",
      provider_refund_id: before?.provider_refund_id,
      provider_result_code: before?.provider_result_code,
      canonical_sha256: before?.canonical_sha256,
      medusa_refund_id: "ref_locally_completed",
    });
  });

  test("an out-of-band same-capture same-amount refund does not consume an unknown local reservation", async () => {
    const requestId = randomUUID();
    const captureId = "8ac7a4a284c684140184c7a8f19a5530";
    await createPeachRefundDispatch(db, {
      request_id: requestId,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: captureId,
      amount_minor: 500,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 500 },
      status: "requested",
    });
    await db("storefront_peach_refund_dispatch").where({ request_id: requestId }).update({ status: "unknown" });

    const event = {
      webhook_id: `refund-${randomUUID()}`,
      checkout_id: "",
      merchant_reference: "",
      amount_minor: 500,
      currency_code: "ZAR",
      payment_type: "RF",
      result_code: "000.100.110",
      transaction_id: "8ac7a49f8af08e94018af09246760e30",
      referenced_transaction_id: captureId,
      refund_request_id: null,
      event_timestamp: new Date().toISOString(),
      raw_sha256: "a".repeat(64),
      canonical_sha256: "d".repeat(64),
    };
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      status: "needs_review", provider_outcome: "unknown", request_id: null, external_order_id: null,
      amount_minor: 500, currency_code: "ZAR", provider_refund_id: event.transaction_id,
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(persistAndProcessRefundObservation({} as MedusaContainer, db, event, "webhook", fetcher as typeof fetch))
      .resolves.toBe("needs_review");
    const local = await findPeachRefundDispatch(db, requestId);
    expect(local?.status).toBe("unknown");
    expect(local?.provider_refund_id).toBeNull();
    const payload = JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body));
    expect(payload).not.toHaveProperty("request_id");
    expect(payload).toMatchObject({ referenced_capture_id: captureId, amount_minor: 500, signature_verified: true });
  });

  test("a signed synchronous refund response remains a response event through inbox processing", async () => {
    const event = {
      webhook_id: null,
      checkout_id: "",
      merchant_reference: "",
      amount_minor: 500,
      currency_code: "ZAR",
      payment_type: "RF",
      result_code: "000.100.110",
      transaction_id: randomUUID().replaceAll("-", ""),
      referenced_transaction_id: "8ac7a4a284c684140184c7a8f19a5530",
      refund_request_id: null,
      event_timestamp: new Date().toISOString(),
      raw_sha256: "a".repeat(64),
      canonical_sha256: "b".repeat(64),
    };
    const inbox = await receivePeachWebhook(db, event, null, "refund-response");
    const claimed = await claimPeachWebhook(db, inbox.id);
    if (!claimed) throw new Error("Signed response inbox row was not claimable");
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      status: "needs_review",
      provider_outcome: "unknown",
      resolution_code: "binding_capture_not_uniquely_matched",
      amount_minor: event.amount_minor,
      currency_code: event.currency_code,
      provider_refund_id: event.transaction_id,
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(processClaimedPeachRefundWebhook(
      {} as MedusaContainer, db, claimed, fetcher as typeof fetch,
    )).resolves.toBe("needs_review");
    expect(fetcher).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body)) as Record<string, unknown>;
    expect(payload).toMatchObject({
      event_source: "response",
      provider_refund_id: event.transaction_id,
      referenced_capture_id: event.referenced_transaction_id,
      signature_verified: true,
    });
    expect(payload).not.toHaveProperty("webhook_id");
    expect(payload).not.toHaveProperty("request_id");
  });

  test("a conflicting signed refund response stays in its inbox and cannot rewrite a succeeded local refund", async () => {
    const requestId = randomUUID();
    const captureId = "8ac7a4a284c684140184c7a8f19a5530";
    const originalProviderRefundId = randomUUID().replaceAll("-", "");
    const conflictingProviderRefundId = randomUUID().replaceAll("-", "");
    const originalDigest = "c".repeat(64);
    const capability = randomUUID();
    const medusaPaymentId = `pay_${randomUUID()}`;
    const medusaRefundId = `ref_${randomUUID()}`;
    await createPeachRefundDispatch(db, {
      request_id: requestId,
      handoff_id: randomUUID(),
      external_order_id: `order-${randomUUID()}`,
      original_transaction_id: captureId,
      amount_minor: 500,
      currency_code: "ZAR",
      cancel_order: false,
      allocation: { line_a: 500 },
      status: "requested",
    });
    await db("storefront_peach_refund_dispatch").where({ request_id: requestId }).update({
      status: "succeeded",
      firstout_status: "succeeded",
      provider_refund_id: originalProviderRefundId,
      provider_result_code: "000.100.110",
      canonical_sha256: originalDigest,
      medusa_payment_id: medusaPaymentId,
      medusa_refund_id: medusaRefundId,
      authorization_key: capability,
    });

    const event = {
      webhook_id: null,
      checkout_id: "",
      merchant_reference: "",
      amount_minor: 500,
      currency_code: "ZAR",
      payment_type: "RF",
      result_code: "000.100.110",
      transaction_id: conflictingProviderRefundId,
      referenced_transaction_id: captureId,
      refund_request_id: requestId,
      event_timestamp: new Date().toISOString(),
      raw_sha256: "a".repeat(64),
      canonical_sha256: "c".repeat(64),
    };
    const inbox = await receivePeachWebhook(db, event, null, "refund-response");
    const claimed = await claimPeachWebhook(db, inbox.id);
    if (!claimed) throw new Error("Conflicting refund event was not claimable");
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      status: "needs_review",
      provider_outcome: "succeeded",
      resolution_code: "binding_provider_refund_id_mismatch",
      request_id: null,
      external_order_id: null,
      handoff_id: null,
      amount_minor: 500,
      currency_code: "ZAR",
      provider_refund_id: conflictingProviderRefundId,
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(persistAndProcessRefundObservation(
      {} as MedusaContainer, db, claimed, "refund-response", fetcher as typeof fetch,
    )).resolves.toBe("needs_review");
    await completePeachWebhook(db, claimed.id, claimed.lease_token, "needs_review");

    const local = await findPeachRefundDispatch(db, requestId);
    expect(local).toMatchObject({
      status: "succeeded",
      firstout_status: "succeeded",
      provider_refund_id: originalProviderRefundId,
      provider_result_code: "000.100.110",
      canonical_sha256: originalDigest,
      medusa_payment_id: medusaPaymentId,
      medusa_refund_id: medusaRefundId,
      authorization_key: capability,
    });
    const storedEvent = await db("storefront_peach_webhook_inbox").where({ id: claimed.id }).first();
    expect(storedEvent).toMatchObject({
      status: "needs_review",
      transaction_id: conflictingProviderRefundId,
      referenced_transaction_id: captureId,
      refund_request_id: requestId,
      canonical_sha256: "c".repeat(64),
    });
    const body = JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body));
    expect(body).toMatchObject({
      request_id: requestId,
      provider_refund_id: conflictingProviderRefundId,
      referenced_capture_id: captureId,
      signature_verified: true,
    });
  });

  test("rejects unauthorized capture and accepts a later paid event after decline", async () => {
    const sessionId = `session-${randomUUID()}`;
    const { attempt } = await createPeachAttempt(db, { paymentSessionId: sessionId, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePeachAttempt(db, attempt.id, {
      checkout_id: "checkout-1", status: "declined", last_event_timestamp: "2026-09-30T11:59:00Z",
      last_event_state: "declined",
    });
    const provider = new StorefrontPeachPaymentProvider({
      [ContainerRegistrationKeys.PG_CONNECTION]: db,
    });
    const sessionData = {
      peach_merchant_reference: attempt.merchant_reference,
      peach_status: "paid",
      peach_amount_minor: 1000,
      peach_checkout_id: "checkout-1",
      currency_code: "ZAR",
    };
    const authorizeInput: AuthorizePaymentInput = { data: sessionData, context: { idempotency_key: sessionId } };
    await expect(provider.authorizePayment(authorizeInput)).rejects.toThrow(/not verified as captured/i);

    const paidEvent = webhook(`late-paid-${randomUUID()}`, attempt.merchant_reference,
      "2026-09-30T12:00:00Z", "000.000.000");
    const webhookPayload: ProviderWebhookPayload["payload"] = {
      data: { ...paidEvent }, rawData: JSON.stringify(paidEvent), headers: {},
    };
    const action = await provider.getWebhookActionAndData(webhookPayload);
    expect(action.action).toBe(PaymentActions.NOT_SUPPORTED);
    expect(peachEventCanAdvance({ ...attempt, status: "declined", last_event_timestamp: "2026-09-30T11:59:00Z" }, {
      event_timestamp: paidEvent.event_timestamp, result_state: "paid",
    })).toBe(true);

    await updatePeachAttempt(db, attempt.id, {
      status: "captured", last_event_timestamp: paidEvent.event_timestamp, last_event_state: "paid",
    });
    expect((await provider.getWebhookActionAndData(webhookPayload)).action).toBe(PaymentActions.SUCCESSFUL);
    const lateDecline = webhook(`late-decline-${randomUUID()}`, attempt.merchant_reference,
      "2026-09-30T12:01:00Z", "800.100.153");
    expect((await provider.getWebhookActionAndData({
      data: { ...lateDecline }, rawData: JSON.stringify(lateDecline), headers: {},
    })).action).toBe(PaymentActions.NOT_SUPPORTED);
    const authorized = await provider.authorizePayment(authorizeInput);
    expect(authorized).toMatchObject({
      status: PaymentSessionStatus.CAPTURED,
      data: { peach_authorized_payment_session_id: sessionId, peach_status: "captured" },
    });
    const verifiedCaptureInput: CapturePaymentInput = {
      data: authorized.data, context: { idempotency_key: `capture-${randomUUID()}` },
    };
    await expect(provider.capturePayment(verifiedCaptureInput)).rejects.toThrow(/separate Peach capture is unsupported/i);
    await db("storefront_peach_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("re-reads captured state after waiting for the shared lock before applying an older callback", async () => {
    const { attempt } = await createPeachAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePeachAttempt(db, attempt.id, { checkout_id: "checkout-1", status: "checkout_created" });
    const event = webhook(`race-${randomUUID()}`, attempt.merchant_reference, "2026-09-30T11:59:59Z", "000.200.000");
    const inbox = await receivePeachWebhook(db, event, "signature");
    const claimed = await claimPeachWebhook(db, inbox.id);
    if (!claimed) throw new Error("Test webhook claim was not created");

    let enteredLock!: () => void;
    let releaseLock!: () => void;
    const lockEntered = new Promise<void>((resolve) => { enteredLock = resolve; });
    const lockGate = new Promise<void>((resolve) => { releaseLock = resolve; });
    const locking = { execute: async (_key: string, operation: () => Promise<unknown>) => {
      enteredLock();
      await lockGate;
      return operation();
    } };
    const container = {
      resolve(key: string) {
        if (key === Modules.LOCKING) return locking;
        throw new Error("The stale callback should stop before resolving other services");
      },
    } as unknown as MedusaContainer;

    const processing = processClaimedPeachWebhook(container, db, claimed);
    await lockEntered;
    await updatePeachAttempt(db, attempt.id, {
      status: "captured", last_event_timestamp: "2026-09-30T12:00:00Z", last_event_state: "paid",
    });
    releaseLock();
    await expect(processing).resolves.toBe("ignored");

    const storedAttempt = await findPeachAttemptByReference(db, attempt.merchant_reference);
    expect(storedAttempt?.status).toBe("captured");
    expect(peachEventCanAdvance(storedAttempt!, claimed)).toBe(false);
    const inboxRow = await db("storefront_peach_webhook_inbox").where({ id: claimed.id }).first();
    expect(inboxRow.status).toBe("ignored");
  });

  test("continues durable inbox processing when the Firstout refund feed is unavailable", async () => {
    await db("storefront_peach_payment_attempt").whereNull("deleted_at").update({ status: "captured" });
    await db("storefront_peach_webhook_inbox").whereNull("deleted_at")
      .whereIn("status", ["received", "retry", "processing"])
      .update({ status: "ignored", lease_until: null, lease_token: null, next_attempt_at: null });

    const event = { ...webhook(`job-feed-outage-${randomUUID()}`, "TestReference01", new Date().toISOString(), "800.100.153"),
      payment_type: "CD" };
    const inbox = await receivePeachWebhook(db, event, "synthetic-signature");
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response("unavailable", { status: 503 }));
    const container = {
      resolve(key: string) {
        if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
        throw new Error(`Unexpected Medusa service ${key}`);
      },
    } as unknown as MedusaContainer;
    const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    try {
      await processPeachWebhooksJob(container, fetcher as typeof fetch);
    } finally {
      warn.mockRestore();
    }

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0]?.[0])).toContain("refund-commands?limit=100");
    expect(await db("storefront_peach_webhook_inbox").where({ id: inbox.id }).first()).toMatchObject({ status: "ignored" });
  });
});
