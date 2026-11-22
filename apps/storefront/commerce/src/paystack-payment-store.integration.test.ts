import knexFactory, { type Knex } from "knex";
import { randomUUID } from "node:crypto";
import { ContainerRegistrationKeys, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { AuthorizePaymentInput, CapturePaymentInput, MedusaContainer, ProviderWebhookPayload } from "@medusajs/framework/types";
import {
  claimPaystackAttemptStatusCheck, claimPaystackObservation, claimPaystackRefundDispatchForDispatch, claimPaystackRefundForMedusa,
  completePaystackObservation, createPaystackAttempt, createPaystackRefundDispatch, findPaystackAttemptByReference,
  findPaystackRefundDispatch, listPaystackAttemptsForStatusCheck, paystackEventCanAdvance, receivePaystackObservation,
  updatePaystackAttempt, updatePaystackRefundDispatch,
} from "./paystack-payment-store";
import { processClaimedPaystackObservation, reconcilePaystackCheckoutStatuses } from "./paystack-webhook-processing";
import { parsePaystackRefund, parsePaystackVerifyResponse, paystackRefundReference, type PaystackObservation } from "./paystack-checkout";
import { StorefrontPaystackPaymentProvider } from "./modules/storefront-paystack-payment-provider/service";
import { Migration20261121123916 } from "./modules/storefront-paystack/migrations/Migration20261121123916";
import { Migration20261122153000 } from "./modules/storefront-refund-cutover/migrations/Migration20261122153000";
import processPaystackWebhooksJob from "./jobs/process-paystack-webhooks";
import { paystackAttemptFinding } from "./storefront-exception-sources";
import {
  processClaimedPaystackRefund, reconcilePaystackRefundsForCapture, syncStorefrontPaystackRefundCommands,
} from "./storefront-paystack-refunds";

const databaseUrl = process.env.STOREFRONT_PG_TEST_URL;
const describeWithPostgres = databaseUrl ? describe : describe.skip;

function charge(reference: string, status: string, timestamp: string, amount = 1000): PaystackObservation {
  const observation = parsePaystackVerifyResponse({
    status: true,
    data: { id: 4099260516, status, reference, amount, currency: "ZAR", paid_at: timestamp, created_at: timestamp },
  }, reference);
  if (!observation) throw new Error("Test charge fixture is invalid");
  return observation;
}

function refundObservation(input: {
  providerRefundId: string; capture: string; amount: number; status: string; requestId: string | null; marker?: string;
}): PaystackObservation {
  const observation = parsePaystackRefund({
    id: input.providerRefundId, transaction: 4099260516, reference: input.requestId ? paystackRefundReference(input.requestId) : `TRF_${input.marker || "x"}`,
    amount: input.amount, currency: "ZAR", status: input.status, created_at: new Date().toISOString(),
  }, { reference: input.capture, transactionId: "4099260516", refundRequestId: input.requestId });
  if (!observation) throw new Error("Test refund fixture is invalid");
  return observation;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describeWithPostgres("Paystack durable inbox (isolated PostgreSQL)", () => {
  let admin: Knex;
  let db: Knex;
  let schema: string;
  const envKeys = [
    "FIRSTOUT_OPS_URL", "FIRSTOUT_OPS_TOKEN", "FIRSTOUT_OPS_COMPANY_ID",
    "PAYSTACK_SECRET_KEY", "PAYSTACK_WEBHOOK_SECRET", "PAYSTACK_LIVE_ENABLED", "PAYSTACK_REFUNDS_PAUSED", "PAYSTACK_HOSTED_TEST_MODE", "STOREFRONT_PUBLIC_URL",
  ] as const;
  const originalEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]));
  const locking = { execute: async (_key: string, operation: () => Promise<unknown>) => operation() };
  const dbContainer = () => ({
    resolve(key: string) {
      if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
      if (key === Modules.LOCKING) return locking;
      throw new Error(`Unexpected Medusa service ${key}`);
    },
  }) as unknown as MedusaContainer;

  beforeAll(async () => {
    Object.assign(process.env, {
      FIRSTOUT_OPS_URL: "https://firstout.invalid/api/v1/ops-commerce/v1",
      FIRSTOUT_OPS_TOKEN: "disposable-test-token",
      FIRSTOUT_OPS_COMPANY_ID: "disposable-test-company",
      PAYSTACK_SECRET_KEY: "sk_test_disposable",
      PAYSTACK_WEBHOOK_SECRET: "whsec_disposable",
      PAYSTACK_LIVE_ENABLED: "false",
      PAYSTACK_REFUNDS_PAUSED: "false",
      // Jest is not an explicit local Medusa command, so the runtime counts as hosted.
      PAYSTACK_HOSTED_TEST_MODE: "true",
      STOREFRONT_PUBLIC_URL: "http://localhost:3004",
    });
    admin = knexFactory({ client: "pg", connection: databaseUrl });
    schema = `paystack_test_${randomUUID().replaceAll("-", "")}`;
    await admin.raw("CREATE SCHEMA ??", [schema]);
    db = knexFactory({ client: "pg", connection: databaseUrl, searchPath: [schema] });
    const migrationSql: string[] = [];
    for (const Migration of [Migration20261121123916, Migration20261122153000]) {
      const collector: InstanceType<typeof Migration> = Object.create(Migration.prototype);
      Reflect.set(collector, "addSql", (statement: string) => migrationSql.push(statement));
      await collector.up();
    }
    for (const statement of migrationSql) await db.raw(statement);
  });

  afterAll(async () => {
    if (db) await db.destroy();
    if (admin && schema) {
      await admin.raw("DROP SCHEMA ?? CASCADE", [schema]);
      await admin.destroy();
    }
    for (const key of envKeys) {
      const value = originalEnv[key];
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });

  test("persists the attempt and reference before initialize, then keeps a deleted-session capture in the inbox", async () => {
    const sessionId = `session-deleted-${randomUUID()}`;
    const cartId = `cart-original-${randomUUID()}`;
    const snapshot = { id: cartId, total: 10, currency_code: "zar", items: [{ id: "item_original", quantity: 1 }] };
    const provider = new StorefrontPaystackPaymentProvider({ [ContainerRegistrationKeys.PG_CONNECTION]: db });
    let initializeBody: Record<string, unknown> = {};
    const boundary = jest.spyOn(global, "fetch").mockImplementation(async (url, init) => {
      expect(String(url)).toBe("https://api.paystack.co/transaction/initialize");
      expect((init?.headers as Record<string, string>).authorization).toBe("Bearer sk_test_disposable");
      // This assertion runs at the external boundary, before Paystack could take money.
      const durable = await db("storefront_paystack_payment_attempt").where({ payment_session_id: sessionId }).first();
      expect(durable).toMatchObject({ cart_id: cartId, checkout_snapshot: snapshot, status: "initiating" });
      initializeBody = JSON.parse(String(init?.body));
      return json({ status: true, data: {
        authorization_url: "https://checkout.paystack.com/abc123", access_code: "abc123", reference: durable.reference,
      } });
    });
    let output;
    try {
      await expect(provider.initiatePayment({ amount: 10, currency_code: "zar", context: { idempotency_key: sessionId },
        data: { storefront_cart_id: cartId, storefront_checkout_snapshot: snapshot } })).rejects.toThrow(/email/i);
      output = await provider.initiatePayment({ amount: 10, currency_code: "zar", context: { idempotency_key: sessionId },
        data: { storefront_cart_id: cartId, storefront_checkout_snapshot: snapshot, storefront_customer_email: "buyer@example.test" } });
      // A repeated initiation returns the stored checkout without a second POST.
      await provider.initiatePayment({ amount: 10, currency_code: "zar", context: { idempotency_key: sessionId },
        data: { storefront_customer_email: "buyer@example.test" } });
      expect(boundary).toHaveBeenCalledTimes(1);
    } finally {
      boundary.mockRestore();
    }
    const attempt = await db("storefront_paystack_payment_attempt").where({ payment_session_id: sessionId }).first();
    expect(initializeBody).toEqual({
      email: "buyer@example.test", amount: 1000, currency: "ZAR", reference: attempt.reference,
      callback_url: "http://localhost:3004/checkout/paystack-return",
      metadata: { payment_session_id: sessionId, cart_id: cartId },
    });
    expect(output).toMatchObject({ status: PaymentSessionStatus.PENDING, data: {
      paystack_status: "checkout_created", redirect_url: "https://checkout.paystack.com/abc123",
    } });
    expect(attempt.checkout_snapshot).not.toHaveProperty("storefront_customer_email");

    const event = charge(attempt.reference, "success", new Date().toISOString());
    const inbox = await receivePaystackObservation(db, event, "webhook", "verified-test-signature");
    const claimed = await claimPaystackObservation(db, inbox.id);
    if (!claimed) throw new Error("Paid inbox row was not claimable");
    const graph = async ({ entity }: { entity: string }) => {
      if (entity === "payment_session" || entity === "cart") return { data: [] };
      throw new Error(`Unexpected graph entity ${entity}`);
    };
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    expect(await processClaimedPaystackObservation(container, db, claimed)).toBe("paid_exception");
    expect(await findPaystackAttemptByReference(db, attempt.reference)).toMatchObject({
      cart_id: cartId, checkout_snapshot: snapshot, status: "captured", transaction_id: "4099260516", last_event_state: "paid",
    });
    expect(await db("storefront_paystack_webhook_inbox").where({ id: claimed.id }).first()).toMatchObject({
      status: "paid_exception", lease_token: null, kind: "charge", provider_status: "success",
    });
    expect(await claimPaystackObservation(db, inbox.id)).toBeUndefined();
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("an ambiguous initialize stays unknown and is reconciled only by the verify endpoint", async () => {
    const sessionId = `session-timeout-${randomUUID()}`;
    const provider = new StorefrontPaystackPaymentProvider({ [ContainerRegistrationKeys.PG_CONNECTION]: db });
    const boundary = jest.spyOn(global, "fetch").mockImplementation(async () => { throw new Error("timeout"); });
    try {
      const output = await provider.initiatePayment({ amount: 10, currency_code: "zar", context: { idempotency_key: sessionId },
        data: { storefront_customer_email: "buyer@example.test" } });
      expect(output).toMatchObject({ status: PaymentSessionStatus.PENDING, data: { paystack_status: "initiation_unknown" } });
    } finally {
      boundary.mockRestore();
    }
    const attempt = await db("storefront_paystack_payment_attempt").where({ payment_session_id: sessionId }).first();
    expect(attempt.status).toBe("initiation_unknown");
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("deduplicates identical facts and atomically permits one concurrent claim", async () => {
    const event = charge(`dk_dedupe_${randomUUID().slice(0, 8)}`, "abandoned", new Date().toISOString());
    const first = await receivePaystackObservation(db, event, "webhook", "signature-a");
    const replay = await receivePaystackObservation(db, event, "status");
    expect(replay).toEqual({ id: first.id, duplicate: true });

    const claims = await Promise.all([claimPaystackObservation(db, first.id), claimPaystackObservation(db, first.id)]);
    expect(claims.filter(Boolean)).toHaveLength(1);
    const claimed = claims.find(Boolean)!;
    expect(claimed.lease_token).toMatch(/^[a-f\d-]{36}$/i);
    // A DB timestamp with microseconds cannot round-trip through JS Date, so
    // completion must fence on the opaque token rather than lease_until.
    await db("storefront_paystack_webhook_inbox").where({ id: claimed.id }).update({
      lease_until: db.raw("'2026-09-30T12:00:00.123456Z'::timestamptz"),
    });
    await completePaystackObservation(db, claimed.id, claimed.lease_token, "processed");
    expect(await claimPaystackObservation(db, first.id)).toBeUndefined();
  });

  test("uses the active partial index for idempotency and preserves exact minor amounts above int32", async () => {
    const event = charge(`dk_softdel_${randomUUID().slice(0, 8)}`, "abandoned", new Date().toISOString());
    const first = await receivePaystackObservation(db, event, "webhook");
    await db("storefront_paystack_webhook_inbox").where({ id: first.id }).update({ deleted_at: new Date() });
    const replacement = await receivePaystackObservation(db, event, "webhook");
    expect(replacement.duplicate).toBe(false);
    expect(replacement.id).not.toBe(first.id);

    const amountMinor = 4_000_000_000;
    const attempt = await createPaystackAttempt(db, { paymentSessionId: `large-session-${randomUUID()}`, amountMinor, currencyCode: "ZAR" });
    const inbox = await receivePaystackObservation(db, charge(attempt.attempt.reference, "abandoned", new Date().toISOString(), amountMinor), "status");
    const storedAttempt = await db("storefront_paystack_payment_attempt").where({ id: attempt.attempt.id }).first();
    const storedEvent = await db("storefront_paystack_webhook_inbox").where({ id: inbox.id }).first();
    expect(Number(storedAttempt.amount_minor)).toBe(amountMinor);
    expect(storedAttempt.raw_amount_minor).toEqual({ value: String(amountMinor), precision: 20 });
    expect(Number(storedEvent.amount_minor)).toBe(amountMinor);
    expect(storedEvent.raw_amount_minor).toEqual({ value: String(amountMinor), precision: 20 });
  });

  test("concurrent refund command creation converges on one immutable dispatch and one provider claim", async () => {
    const requestId = randomUUID();
    const command = {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: "dk_capture_concurrent", amount_minor: 1250, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 750, line_b: 500 }, status: "requested",
    };
    const created = await Promise.all([createPaystackRefundDispatch(db, command), createPaystackRefundDispatch(db, command)]);
    expect(new Set(created.map((value) => value.dispatch.id)).size).toBe(1);
    expect(created.map((value) => value.created).sort()).toEqual([false, true]);
    await expect(createPaystackRefundDispatch(db, { ...command, allocation: { line_a: 749, line_b: 501 } }))
      .rejects.toThrow(/changed after it was durably received/i);

    const claims = await Promise.all([
      claimPaystackRefundDispatchForDispatch(db, requestId), claimPaystackRefundDispatchForDispatch(db, requestId),
    ]);
    expect(claims.filter(Boolean)).toHaveLength(1);
    expect((await findPaystackRefundDispatch(db, requestId))?.status).toBe("dispatching");
    expect(await claimPaystackRefundDispatchForDispatch(db, requestId)).toBe(false);
  });

  test("native Medusa refund capability can be consumed only by the matching verified intent", async () => {
    const requestId = randomUUID();
    await createPaystackRefundDispatch(db, {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: "dk_capture_capability", amount_minor: 500, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 500 }, status: "requested",
    });
    const providerRefundId = "3018000";
    const capability = randomUUID();
    await db("storefront_paystack_refund_dispatch").where({ request_id: requestId }).update({
      status: "verified", provider_refund_id: providerRefundId, authorization_key: capability,
    });
    const input = { requestId, providerRefundId, capability, paymentId: `pay_${randomUUID()}`, refundId: `ref_${randomUUID()}`, amountMinor: 500 };
    await updatePaystackRefundDispatch(db, requestId, { medusa_payment_id: `pay_${randomUUID()}` });
    const boundPaymentId = (await findPaystackRefundDispatch(db, requestId))?.medusa_payment_id;
    expect(await claimPaystackRefundForMedusa(db, input)).toBe(false);
    input.paymentId = boundPaymentId!;
    expect(await claimPaystackRefundForMedusa(db, input)).toBe(true);
    expect(await claimPaystackRefundForMedusa(db, input)).toBe(true);
    expect(await claimPaystackRefundForMedusa(db, { ...input, refundId: `ref_${randomUUID()}` })).toBe(false);
    expect((await findPaystackRefundDispatch(db, requestId))?.status).toBe("recording_medusa_refund");
  });

  test("recovers remote dispatching commands as unknown without ever posting a Paystack refund", async () => {
    const commands = ["dispatching", "received"].map((localStatus) => ({
      request_id: randomUUID(), handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: `dk_${randomUUID().replaceAll("-", "")}`, amount_minor: 1250, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 1250 }, status: "dispatching", local_status: localStatus,
    }));
    for (const command of commands) {
      await createPaystackRefundDispatch(db, command);
      await updatePaystackRefundDispatch(db, command.request_id, { status: command.local_status });
    }
    const outcomeBodies: Record<string, unknown>[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("refund-commands?limit=100")) return json({ items: commands.map(({ local_status: _local, ...command }) => command) });
      if (url.includes("/refund-commands/") && url.endsWith("/outcome")) {
        outcomeBodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
        return json({ status: "unknown" });
      }
      throw new Error(`Unexpected external request ${url}`);
    });

    await expect(syncStorefrontPaystackRefundCommands(dbContainer(), fetcher as typeof fetch))
      .resolves.toEqual({ received: commands.length, dispatched: commands.length });
    expect(fetcher).toHaveBeenCalledTimes(1 + commands.length);
    expect(fetcher.mock.calls.some(([input]) => String(input).includes("api.paystack.co"))).toBe(false);
    expect(outcomeBodies.every((body) => body.status === "unknown")).toBe(true);
    for (const command of commands) {
      expect(await findPaystackRefundDispatch(db, command.request_id)).toMatchObject({ status: "unknown", provider_refund_id: null });
    }
  });

  test("posts one refund with our deterministic reference only after Firstout confirms dispatching", async () => {
    const requestId = randomUUID();
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR" });
    const externalOrderId = `order-${randomUUID()}`;
    await updatePaystackAttempt(db, attempt.id, { status: "captured", transaction_id: "5000000001", captured_order_id: externalOrderId });
    const command = {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: externalOrderId,
      original_transaction_id: attempt.reference, amount_minor: 2500, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 2500 }, status: "requested",
    };
    const calls: string[] = [];
    let refundBody: Record<string, unknown> = {};
    let firstoutEvent: Record<string, unknown> = {};
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (url.endsWith("refund-commands?limit=100")) return json({ items: [command] });
      if (url.endsWith(`/refund-commands/${requestId}/outcome`)) {
        const body = JSON.parse(String(init?.body));
        return json({ id: requestId, status: body.status, amount_minor: 2500, currency_code: "ZAR" });
      }
      if (url === "https://api.paystack.co/refund") {
        refundBody = JSON.parse(String(init?.body));
        return json({ status: true, data: {
          id: 3018284, reference: paystackRefundReference(requestId), amount: 2500, currency: "ZAR", status: "pending",
          createdAt: "2026-11-21T09:21:17.122Z", transaction: { id: 5000000001, reference: attempt.reference },
        } });
      }
      if (url.endsWith("/refund-events")) {
        firstoutEvent = JSON.parse(String(init?.body));
        return json({ status: "pending", provider_outcome: "pending", request_id: requestId, external_order_id: command.external_order_id,
          amount_minor: 2500, currency_code: "ZAR", provider_refund_id: "3018284", duplicate: false });
      }
      if (url.includes("/refund?transaction=")) return json({ status: true, data: [] });
      throw new Error(`Unexpected external request ${url}`);
    });
    const graph = jest.fn(async () => ({ data: [{ id: command.external_order_id, display_id: 1, email: "buyer@example.test", metadata: {} }] }));
    const updateOrders = jest.fn(async () => []);
    const container = { resolve(key: string) {
      if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      if (key === Modules.ORDER) return { updateOrders };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;

    await syncStorefrontPaystackRefundCommands(container, fetcher as typeof fetch);
    expect(calls.filter((url) => url === "https://api.paystack.co/refund")).toHaveLength(1);
    expect(calls.indexOf("https://api.paystack.co/refund")).toBeGreaterThan(calls.findIndex((url) => url.endsWith("/outcome")));
    expect(refundBody).toEqual({ transaction: attempt.reference, amount: 2500, currency: "ZAR", reference: paystackRefundReference(requestId) });
    expect(firstoutEvent).toMatchObject({
      request_id: requestId, provider_refund_id: "3018284", event_source: "response", referenced_capture_id: attempt.reference,
      result_code: "pending", outcome: "pending", signature_verified: true,
    });
    expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({ status: "pending", provider_refund_id: "3018284" });

    // The same command seen again is not re-posted.
    await syncStorefrontPaystackRefundCommands(container, fetcher as typeof fetch);
    expect(calls.filter((url) => url === "https://api.paystack.co/refund")).toHaveLength(1);
  });

  test("leaves a new refund command untouched while legacy dispatch is closed", async () => {
    const requestId = randomUUID();
    const { attempt } = await createPaystackAttempt(db, {
      paymentSessionId: `session-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR",
    });
    const orderId = `order-${randomUUID()}`;
    await updatePaystackAttempt(db, attempt.id, {
      status: "captured", transaction_id: "5000000088", captured_order_id: orderId,
    });
    const command = {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: orderId,
      original_transaction_id: attempt.reference, amount_minor: 2500, currency_code: "ZAR",
      cancel_order: false, allocation: {}, status: "requested",
    };
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("refund-commands?limit=100")) return json({ items: [command] });
      if (!init?.method && String(input).includes("/refund?transaction=")) return json({ status: true, data: [] });
      throw new Error("Deferred refund sent a write request");
    });

    await db("storefront_refund_cutover").where({ id: "medusa-refunds" }).update({ phase: "legacy_closed" });
    try {
      await expect(syncStorefrontPaystackRefundCommands(dbContainer(), fetcher))
        .resolves.toEqual({ received: 1, dispatched: 0 });
      expect(await findPaystackRefundDispatch(db, requestId)).toBeUndefined();
      expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toEqual([]);
    } finally {
      await db("storefront_refund_cutover").where({ id: "medusa-refunds" }).update({ phase: "legacy_open" });
    }
  });

  test("preserves a provider-confirmed refund for replay when the native writer is deferred", async () => {
    const requestId = randomUUID();
    const capture = `dk_${randomUUID().replaceAll("-", "")}`;
    const orderId = `order-${randomUUID()}`;
    const event = refundObservation({
      providerRefundId: "3019991", capture, amount: 2500, status: "processed", requestId,
    });
    const providerWrite = jest.fn(async () => ({}));
    const graph = async () => ({ data: [{
      id: orderId,
      payment_collections: [{ payments: [{
        id: "pay_fixture", provider_id: "pp_paystack_checkout", data: { transaction_id: capture },
      }] }],
    }] });
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      if (key === Modules.PAYMENT) return {
        refundPayment: providerWrite,
      };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    const fetcher = jest.fn(async () => json({
      status: "succeeded", provider_outcome: "succeeded", request_id: requestId, external_order_id: orderId,
      amount_minor: 2500, currency_code: "ZAR", provider_refund_id: "3019991",
    }));

    await db("storefront_refund_cutover").where({ id: "medusa-refunds" }).update({ phase: "legacy_closed" });
    try {
      await expect(processClaimedPaystackRefund(container, db, event, fetcher))
        .rejects.toMatchObject({ code: "storefront_refunds_temporarily_deferred" });
      expect(providerWrite).not.toHaveBeenCalled();
      expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({
        status: "verified", provider_refund_id: "3019991", medusa_payment_id: "pay_fixture",
      });
    } finally {
      await db("storefront_refund_cutover").where({ id: "medusa-refunds" }).update({ phase: "legacy_open" });
    }
  });

  test("a 409 duplicate reference is read back and bound by reference, and needs-attention is surfaced, never automated", async () => {
    const requestId = randomUUID();
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR" });
    const externalOrderId = `order-${randomUUID()}`;
    await updatePaystackAttempt(db, attempt.id, { status: "captured", transaction_id: "5000000002", captured_order_id: externalOrderId });
    const command = {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: externalOrderId,
      original_transaction_id: attempt.reference, amount_minor: 1500, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 1500 }, status: "requested",
    };
    const calls: string[] = [];
    const events: Record<string, unknown>[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(`${init?.method || "GET"} ${url}`);
      if (url.endsWith("refund-commands?limit=100")) return json({ items: [command] });
      if (url.endsWith("/outcome")) {
        const body = JSON.parse(String(init?.body));
        return json({ id: requestId, status: body.status, amount_minor: 1500, currency_code: "ZAR" });
      }
      if (url === "https://api.paystack.co/refund") return json({ status: false, message: "exists" }, 409);
      if (url === "https://api.paystack.co/refund?transaction=5000000002&perPage=100") {
        return json({ status: true, data: [
          { id: 9001, transaction: 5000000002, reference: paystackRefundReference(requestId), amount: 1500, currency: "ZAR",
            status: "needs-attention", created_at: "2026-11-21T10:00:00Z" },
        ] });
      }
      if (url.endsWith("/refund-events")) {
        const body = JSON.parse(String(init?.body));
        events.push(body);
        return json({ status: "needs_review", provider_outcome: "unknown", request_id: requestId, external_order_id: command.external_order_id,
          amount_minor: 1500, currency_code: "ZAR", provider_refund_id: "9001", duplicate: false });
      }
      throw new Error(`Unexpected external request ${url}`);
    });

    await syncStorefrontPaystackRefundCommands(dbContainer(), fetcher as typeof fetch);
    expect(calls.filter((call) => call === "POST https://api.paystack.co/refund")).toHaveLength(1);
    expect(calls.some((call) => call.includes("retry_with_customer_details"))).toBe(false);
    expect(events[0]).toMatchObject({ request_id: requestId, provider_refund_id: "9001", result_code: "needs-attention", outcome: "unknown" });
    expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({
      status: "needs_attention", provider_refund_id: "9001", provider_result_code: "needs-attention",
    });
  });

  test("does not downgrade a completed local refund from a stale remote dispatching snapshot", async () => {
    const requestId = randomUUID();
    const command = {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: `dk_${randomUUID().replaceAll("-", "")}`, amount_minor: 1250, currency_code: "ZAR",
      cancel_order: false, allocation: { line_a: 1250 }, status: "dispatching",
    };
    await createPaystackRefundDispatch(db, command);
    await updatePaystackRefundDispatch(db, requestId, {
      status: "succeeded", firstout_status: "succeeded", provider_refund_id: String(Date.now()),
      provider_result_code: "processed", canonical_sha256: "a".repeat(64), medusa_payment_id: null, medusa_refund_id: "ref_locally_completed",
    });
    const before = await findPaystackRefundDispatch(db, requestId);
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => json({ items: [command] }));

    await expect(syncStorefrontPaystackRefundCommands(dbContainer(), fetcher as typeof fetch)).resolves.toEqual({ received: 1, dispatched: 1 });
    // Only the feed read reaches Firstout; read-only reconciliation of other open refunds may query Paystack.
    const calls = fetcher.mock.calls.map(([input]) => String(input));
    expect(calls.filter((url) => !url.startsWith("https://api.paystack.co/refund?"))).toHaveLength(1);
    expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({
      status: "succeeded", firstout_status: "succeeded", provider_refund_id: before?.provider_refund_id,
      provider_result_code: before?.provider_result_code, canonical_sha256: before?.canonical_sha256, medusa_refund_id: "ref_locally_completed",
    });
  });

  test("an out-of-band same-capture same-amount refund does not consume an unknown local reservation", async () => {
    const requestId = randomUUID();
    const capture = "dk_capture_outofband";
    await createPaystackRefundDispatch(db, {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: capture, amount_minor: 500, currency_code: "ZAR", cancel_order: false,
      allocation: { line_a: 500 }, status: "requested",
    });
    await db("storefront_paystack_refund_dispatch").where({ request_id: requestId }).update({ status: "unknown" });
    const event = refundObservation({ providerRefundId: "7777", capture, amount: 500, status: "processed", requestId: null, marker: "dashboard01" });
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => json({
      status: "needs_review", provider_outcome: "unknown", request_id: null, external_order_id: null,
      amount_minor: 500, currency_code: "ZAR", provider_refund_id: "7777",
    }));

    await expect(processClaimedPaystackRefund({} as MedusaContainer, db, event, fetcher as typeof fetch)).resolves.toBe("needs_review");
    const local = await findPaystackRefundDispatch(db, requestId);
    expect(local?.status).toBe("unknown");
    expect(local?.provider_refund_id).toBeNull();
    const payload = JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body));
    expect(payload).not.toHaveProperty("request_id");
    expect(payload).not.toHaveProperty("webhook_id");
    expect(payload).toMatchObject({ referenced_capture_id: capture, amount_minor: 500, event_source: "response", signature_verified: true });
  });

  test("a refund webhook re-reads Paystack and delivers a dashboard refund unbound", async () => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "captured", transaction_id: "5000000003" });
    const events: Record<string, unknown>[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/refund?transaction=5000000003")) {
        return json({ status: true, data: [
          { id: 8123, transaction: 5000000003, reference: "TRF_dashboardmade", amount: 700, currency: "ZAR", status: "processed", created_at: "2026-11-21T10:00:00Z" },
        ] });
      }
      if (url.endsWith("/refund-events")) {
        events.push(JSON.parse(String(init?.body)));
        return json({ status: "needs_review", provider_outcome: "succeeded", request_id: null, external_order_id: null,
          amount_minor: 700, currency_code: "ZAR", provider_refund_id: "8123" });
      }
      throw new Error(`Unexpected external request ${url}`);
    });
    expect(await reconcilePaystackRefundsForCapture(dbContainer(), attempt.reference, "webhook", fetcher as typeof fetch, "sig")).toBe(1);
    expect(events[0]).not.toHaveProperty("request_id");
    expect(events[0]).toMatchObject({ provider_refund_id: "8123", referenced_capture_id: attempt.reference, outcome: "succeeded" });
    // A redelivered webhook reads the same fact and does not resend it to Firstout.
    expect(await reconcilePaystackRefundsForCapture(dbContainer(), attempt.reference, "webhook", fetcher as typeof fetch, "sig")).toBe(0);
    expect(events).toHaveLength(1);
  });

  test("a conflicting refund observation stays in its inbox and cannot rewrite a succeeded local refund", async () => {
    const requestId = randomUUID();
    const capture = "dk_capture_conflict";
    const capability = randomUUID();
    const medusaPaymentId = `pay_${randomUUID()}`;
    const medusaRefundId = `ref_${randomUUID()}`;
    await createPaystackRefundDispatch(db, {
      request_id: requestId, handoff_id: randomUUID(), external_order_id: `order-${randomUUID()}`,
      original_transaction_id: capture, amount_minor: 500, currency_code: "ZAR", cancel_order: false,
      allocation: { line_a: 500 }, status: "requested",
    });
    await db("storefront_paystack_refund_dispatch").where({ request_id: requestId }).update({
      status: "succeeded", firstout_status: "succeeded", provider_refund_id: "1111", provider_result_code: "processed",
      canonical_sha256: "c".repeat(64), medusa_payment_id: medusaPaymentId, medusa_refund_id: medusaRefundId, authorization_key: capability,
    });
    const event = refundObservation({ providerRefundId: "2222", capture, amount: 500, status: "processed", requestId });
    const inbox = await receivePaystackObservation(db, event, "refund-response");
    const claimed = await claimPaystackObservation(db, inbox.id);
    if (!claimed) throw new Error("Conflicting refund event was not claimable");
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => json({
      status: "needs_review", provider_outcome: "succeeded", resolution_code: "binding_provider_refund_id_mismatch",
      request_id: null, external_order_id: null, handoff_id: null, amount_minor: 500, currency_code: "ZAR", provider_refund_id: "2222",
    }));

    await expect(processClaimedPaystackRefund({} as MedusaContainer, db, claimed, fetcher as typeof fetch)).resolves.toBe("needs_review");
    await completePaystackObservation(db, claimed.id, claimed.lease_token, "needs_review");
    expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({
      status: "succeeded", firstout_status: "succeeded", provider_refund_id: "1111", canonical_sha256: "c".repeat(64),
      medusa_payment_id: medusaPaymentId, medusa_refund_id: medusaRefundId, authorization_key: capability,
    });
    expect(await db("storefront_paystack_webhook_inbox").where({ id: claimed.id }).first()).toMatchObject({
      status: "needs_review", provider_refund_id: "2222", reference: capture, refund_request_id: requestId,
    });
  });

  test("the provider reports a capture only from the stored attempt and its verified observation, never from the body", async () => {
    const sessionId = `session-${randomUUID()}`;
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: sessionId, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "declined", last_event_timestamp: "2026-09-30T11:59:00Z", last_event_state: "declined" });
    const provider = new StorefrontPaystackPaymentProvider({ [ContainerRegistrationKeys.PG_CONNECTION]: db });
    const sessionData = { paystack_reference: attempt.reference, paystack_status: "paid", paystack_amount_minor: 1000, currency_code: "ZAR" };
    const authorizeInput: AuthorizePaymentInput = { data: sessionData, context: { idempotency_key: sessionId } };
    await expect(provider.authorizePayment(authorizeInput)).rejects.toThrow(/not verified as captured/i);

    // A forged body claiming paid cannot complete anything while the attempt is not a verified capture.
    const forged = { reference: attempt.reference, kind: "charge", amount_minor: 1000, currency_code: "ZAR", result_state: "paid" };
    const forgedPayload: ProviderWebhookPayload["payload"] = { data: forged, rawData: JSON.stringify(forged), headers: {} };
    expect((await provider.getWebhookActionAndData(forgedPayload)).action).toBe(PaymentActions.NOT_SUPPORTED);
    const paid = charge(attempt.reference, "success", "2026-09-30T12:00:00Z");
    expect(paystackEventCanAdvance({ status: "declined", last_event_timestamp: "2026-09-30T11:59:00Z" }, {
      event_timestamp: paid.event_timestamp, result_state: "paid",
    })).toBe(true);

    // Captured status alone is not enough either: there must be a verified paid observation.
    await updatePaystackAttempt(db, attempt.id, {
      status: "captured", transaction_id: "4099260516", last_event_timestamp: paid.event_timestamp, last_event_state: "paid",
    });
    expect((await provider.getWebhookActionAndData(forgedPayload)).action).toBe(PaymentActions.NOT_SUPPORTED);
    await expect(provider.authorizePayment(authorizeInput)).rejects.toThrow(/not verified as captured/i);
    // An observation for a different amount does not count.
    await receivePaystackObservation(db, charge(attempt.reference, "success", "2026-09-30T12:00:00Z", 999), "status");
    expect((await provider.getWebhookActionAndData(forgedPayload)).action).toBe(PaymentActions.NOT_SUPPORTED);

    const verified = await receivePaystackObservation(db, paid, "webhook");
    // A verified row that is merely queued is not the processor's call in flight.
    expect((await provider.getWebhookActionAndData(forgedPayload)).action).toBe(PaymentActions.NOT_SUPPORTED);
    const inFlight = await claimPaystackObservation(db, verified.id);
    if (!inFlight) throw new Error("Verified paid observation was not claimable");
    // Body amount and state are ignored; the stored amount is reported.
    const lying = { ...forged, amount_minor: 1, currency_code: "USD", result_state: "declined" };
    expect(await provider.getWebhookActionAndData({ data: lying, rawData: "", headers: {} })).toEqual({
      action: PaymentActions.SUCCESSFUL, data: { session_id: sessionId, amount: 10 },
    });
    expect((await provider.getWebhookActionAndData({ data: { reference: "dk_unknown_reference" }, rawData: "", headers: {} })).action)
      .toBe(PaymentActions.NOT_SUPPORTED);
    await expect(provider.authorizePayment({ data: sessionData, context: { idempotency_key: "another-session" } })).rejects.toThrow(/not verified/i);
    await expect(provider.authorizePayment({ data: { ...sessionData, paystack_reference: "dk_other_reference" }, context: { idempotency_key: sessionId } }))
      .rejects.toThrow(/not verified/i);
    const authorized = await provider.authorizePayment(authorizeInput);
    expect(authorized).toMatchObject({
      status: PaymentSessionStatus.CAPTURED,
      data: { paystack_authorized_payment_session_id: sessionId, paystack_status: "captured", transaction_id: attempt.reference, provider_payment_id: "4099260516" },
    });
    const captureInput: CapturePaymentInput = { data: authorized.data, context: { idempotency_key: `capture-${randomUUID()}` } };
    await expect(provider.capturePayment(captureInput)).rejects.toThrow(/separate Paystack capture is unsupported/i);
    // Once the processor settles the row (here: a paid exception after the hold expired), the hooks refuse again.
    await completePaystackObservation(db, inFlight.id, inFlight.lease_token, "paid_exception");
    expect((await provider.getWebhookActionAndData(forgedPayload)).action).toBe(PaymentActions.NOT_SUPPORTED);
    await expect(provider.authorizePayment(authorizeInput)).rejects.toThrow(/not verified as captured/i);
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test.each([
    ["amount", { amount: 1001, currency: "ZAR" }],
    ["currency", { amount: 1000, currency: "USD" }],
  ])("a verified paid charge with a different %s is kept for review and never captured", async (_label, mismatch) => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "checkout_created" });
    const observation = parsePaystackVerifyResponse({ status: true, data: {
      id: 4099260516, status: "success", reference: attempt.reference, amount: mismatch.amount, currency: mismatch.currency,
      paid_at: new Date().toISOString(), created_at: new Date().toISOString(),
    } }, attempt.reference);
    if (!observation) throw new Error("Mismatch fixture is invalid");
    const inbox = await receivePaystackObservation(db, observation, "webhook", "signature");
    const claimed = await claimPaystackObservation(db, inbox.id);
    if (!claimed) throw new Error("Mismatch observation was not claimable");
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return locking;
      throw new Error("A mismatched charge must stop before touching Medusa");
    } } as unknown as MedusaContainer;
    expect(await processClaimedPaystackObservation(container, db, claimed)).toBe("ignored");
    expect(await db("storefront_paystack_webhook_inbox").where({ id: inbox.id }).first()).toMatchObject({
      status: "needs_review", result_state: "paid", lease_token: null,
    });
    expect(await findPaystackAttemptByReference(db, attempt.reference)).toMatchObject({
      status: "checkout_created", last_event_state: null, captured_order_id: null,
    });
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("polls open and declined attempts for 72 hours, backs off after the first hour, and lets staff target an expired one", async () => {
    await db("storefront_paystack_payment_attempt").whereNull("deleted_at").update({ deleted_at: new Date() });
    const make = async (status: string, ageHours: number, checkedMinutesAgo: number | null) => {
      const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `poll-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
      await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({
        status,
        created_at: db.raw(`NOW() - INTERVAL '${ageHours} hours'`),
        last_status_checked_at: checkedMinutesAgo === null ? null : db.raw(`NOW() - INTERVAL '${checkedMinutesAgo} minutes'`),
      });
      return attempt.id;
    };
    const fresh = await make("checkout_created", 0.1, 2);
    const declined = await make("declined", 2, 20);
    const backedOff = await make("pending", 2, 5);
    const expired = await make("initiation_unknown", 73, null);
    const captured = await make("captured", 0.1, null);
    const due = (await listPaystackAttemptsForStatusCheck(db)).map((row) => row.id);
    expect(due.sort()).toEqual([fresh, declined].sort());
    expect(await claimPaystackAttemptStatusCheck(db, backedOff)).toBe(false);
    expect(await claimPaystackAttemptStatusCheck(db, expired)).toBe(false);
    expect(await claimPaystackAttemptStatusCheck(db, captured)).toBe(false);
    expect(await claimPaystackAttemptStatusCheck(db, declined)).toBe(true);
    expect(await claimPaystackAttemptStatusCheck(db, declined)).toBe(false);
    // Staff repair targets the expired uncertain attempt once per minute.
    expect(await claimPaystackAttemptStatusCheck(db, expired, true)).toBe(true);
    expect(await claimPaystackAttemptStatusCheck(db, expired, true)).toBe(false);
    await db("storefront_paystack_payment_attempt").whereNull("deleted_at").update({ deleted_at: new Date() });
  });

  test("a later success after a declined card is still captured by the status poll", async () => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `retry-card-${randomUUID()}`, cartId: `cart-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "declined", last_event_timestamp: new Date(Date.now() - 60_000).toISOString(), last_event_state: "declined" });
    const calls: string[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return json({ status: true, data: { id: 4099260599, status: "success", reference: attempt.reference, amount: 1000, currency: "ZAR",
        paid_at: new Date().toISOString(), created_at: new Date(Date.now() - 120_000).toISOString() } });
    });
    const container = { resolve(key: string) {
      if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph: async () => ({ data: [] }) };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    expect(await reconcilePaystackCheckoutStatuses(container, undefined, fetcher as typeof fetch)).toBe(1);
    expect(calls).toEqual([`https://api.paystack.co/transaction/verify/${attempt.reference}`]);
    // The native session was deleted in this fixture, so the money is kept as a paid exception for staff.
    expect(await findPaystackAttemptByReference(db, attempt.reference)).toMatchObject({ status: "captured", last_event_state: "paid" });
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("Paystack-confirmed abandonment is stored apart from pending, re-checked, and never alerts", async () => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `abandon-${randomUUID()}`, cartId: `cart-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "checkout_created" });
    const updatePaymentSession = jest.fn(async () => ({}));
    const graph = async ({ entity }: { entity: string }) => {
      if (entity === "payment_session") return { data: [{ id: attempt.payment_session_id, amount: 10, currency_code: "zar", status: "pending",
        provider_id: "pp_paystack_checkout", payment_collection_id: "paycol_abandon", data: {}, metadata: {} }] };
      if (entity === "cart_payment_collection") return { data: [{ cart_id: attempt.cart_id }] };
      if (entity === "order_cart") return { data: [] };
      throw new Error(`Unexpected graph entity ${entity}`);
    };
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      if (key === Modules.PAYMENT) return { updatePaymentSession };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    const observe = async (status: string) => {
      const inbox = await receivePaystackObservation(db, charge(attempt.reference, status, new Date().toISOString()), "status");
      const claimed = await claimPaystackObservation(db, inbox.id);
      if (!claimed) throw new Error("Observation was not claimable");
      return processClaimedPaystackObservation(container, db, claimed);
    };
    expect(await observe("ongoing")).toBe("processed");
    expect((await findPaystackAttemptByReference(db, attempt.reference))?.status).toBe("pending");
    expect(await observe("abandoned")).toBe("processed");
    const stored = await findPaystackAttemptByReference(db, attempt.reference);
    expect(stored).toMatchObject({ status: "abandoned", last_event_state: "pending" });
    expect(updatePaymentSession).toHaveBeenLastCalledWith(expect.objectContaining({ status: PaymentSessionStatus.PENDING }));
    // Still re-checked within the window, because the customer can return to the hosted page.
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ last_status_checked_at: null });
    expect(await claimPaystackAttemptStatusCheck(db, attempt.id)).toBe(true);
    const row = await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).first();
    const longAfter = Date.parse(String(row.created_at)) + 80 * 3_600_000;
    expect(paystackAttemptFinding(row, new Set(), longAfter)).toBeNull();
    await db("storefront_paystack_payment_attempt").where({ id: attempt.id }).update({ deleted_at: new Date() });
  });

  test("never posts a refund for a charge that is not our capture for the same order", async () => {
    const cases = [
      { label: "missing", attempt: null as null | { status: string; orderMatches: boolean } },
      { label: "not captured", attempt: { status: "checkout_created", orderMatches: true } },
      { label: "other order", attempt: { status: "captured", orderMatches: false } },
    ];
    for (const item of cases) {
      const requestId = randomUUID();
      const externalOrderId = `order-${randomUUID()}`;
      let capture = `dk_${randomUUID().replaceAll("-", "")}`;
      if (item.attempt) {
        const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `guard-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR" });
        await updatePaystackAttempt(db, attempt.id, { status: item.attempt.status, transaction_id: "5000000009",
          captured_order_id: item.attempt.orderMatches ? externalOrderId : `order-${randomUUID()}` });
        capture = attempt.reference;
      }
      const command = { request_id: requestId, handoff_id: randomUUID(), external_order_id: externalOrderId,
        original_transaction_id: capture, amount_minor: 1000, currency_code: "ZAR", cancel_order: false, allocation: { a: 1000 }, status: "requested" };
      const calls: string[] = [];
      const outcomes: Record<string, unknown>[] = [];
      const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push(url);
        if (url.endsWith("refund-commands?limit=100")) return json({ items: [command] });
        if (url.endsWith("/outcome")) { outcomes.push(JSON.parse(String(init?.body))); return json({ status: "unknown" }); }
        if (url.includes("/refund?")) return json({ status: true, data: [] });
        throw new Error(`Unexpected external request ${url}`);
      });
      await syncStorefrontPaystackRefundCommands(dbContainer(), fetcher as typeof fetch);
      expect(calls.some((url) => url === "https://api.paystack.co/refund")).toBe(false);
      expect(outcomes).toEqual([{ status: "unknown", failure_code: "paystack_capture_not_verified_no_request_sent" }]);
      expect((await findPaystackRefundDispatch(db, requestId))?.status).toBe("unknown");
    }
  });

  test("an unknown refund on a charge without a Paystack ID is read back by our own reference", async () => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `noid-${randomUUID()}`, amountMinor: 5000, currencyCode: "ZAR" });
    const externalOrderId = `order-${randomUUID()}`;
    await updatePaystackAttempt(db, attempt.id, { status: "captured", captured_order_id: externalOrderId });
    const requestId = randomUUID();
    await createPaystackRefundDispatch(db, { request_id: requestId, handoff_id: randomUUID(), external_order_id: externalOrderId,
      original_transaction_id: attempt.reference, amount_minor: 1200, currency_code: "ZAR", cancel_order: false, allocation: { a: 1200 }, status: "requested" });
    await updatePaystackRefundDispatch(db, requestId, { status: "unknown" });
    const calls: string[] = [];
    const events: Record<string, unknown>[] = [];
    const fetcher = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (url === `https://api.paystack.co/refund?reference=${paystackRefundReference(requestId)}`) {
        return json({ status: true, data: [{ id: 6100, transaction: 5000000077, reference: paystackRefundReference(requestId).toUpperCase(),
          amount: 1200, currency: "ZAR", status: "pending", created_at: "2026-11-21T10:00:00Z" }] });
      }
      if (url.endsWith("/refund-events")) {
        events.push(JSON.parse(String(init?.body)));
        return json({ status: "pending", provider_outcome: "pending", request_id: requestId, external_order_id: externalOrderId,
          amount_minor: 1200, currency_code: "ZAR", provider_refund_id: "6100" });
      }
      throw new Error(`Unexpected external request ${url}`);
    });
    const container = { resolve(key: string) {
      if (key === ContainerRegistrationKeys.PG_CONNECTION) return db;
      if (key === Modules.LOCKING) return locking;
      if (key === ContainerRegistrationKeys.QUERY) return { graph: async () => ({ data: [{ id: externalOrderId, display_id: 1, email: "b@example.test", metadata: {} }] }) };
      if (key === Modules.ORDER) return { updateOrders: async () => [] };
      throw new Error(`Unexpected Medusa service ${key}`);
    } } as unknown as MedusaContainer;
    expect(await reconcilePaystackRefundsForCapture(container, attempt.reference, "status", fetcher as typeof fetch)).toBe(1);
    expect(calls.some((url) => url.includes("transaction="))).toBe(false);
    expect(events[0]).toMatchObject({ request_id: requestId, provider_refund_id: "6100", referenced_capture_id: attempt.reference });
    expect(await findPaystackRefundDispatch(db, requestId)).toMatchObject({ status: "pending", provider_refund_id: "6100" });
  });

  test("re-reads captured state after waiting for the shared lock before applying an older observation", async () => {
    const { attempt } = await createPaystackAttempt(db, { paymentSessionId: `session-${randomUUID()}`, amountMinor: 1000, currencyCode: "ZAR" });
    await updatePaystackAttempt(db, attempt.id, { status: "checkout_created" });
    const inbox = await receivePaystackObservation(db, charge(attempt.reference, "ongoing", "2026-09-30T11:59:59Z"), "status");
    const claimed = await claimPaystackObservation(db, inbox.id);
    if (!claimed) throw new Error("Test observation claim was not created");

    let enteredLock!: () => void;
    let releaseLock!: () => void;
    const lockEntered = new Promise<void>((resolve) => { enteredLock = resolve; });
    const lockGate = new Promise<void>((resolve) => { releaseLock = resolve; });
    const gatedLocking = { execute: async (_key: string, operation: () => Promise<unknown>) => {
      enteredLock();
      await lockGate;
      return operation();
    } };
    const container = { resolve(key: string) {
      if (key === Modules.LOCKING) return gatedLocking;
      throw new Error("The stale observation should stop before resolving other services");
    } } as unknown as MedusaContainer;

    const processing = processClaimedPaystackObservation(container, db, claimed);
    await lockEntered;
    await updatePaystackAttempt(db, attempt.id, { status: "captured", last_event_timestamp: "2026-09-30T12:00:00Z", last_event_state: "paid" });
    releaseLock();
    await expect(processing).resolves.toBe("ignored");
    const storedAttempt = await findPaystackAttemptByReference(db, attempt.reference);
    expect(storedAttempt?.status).toBe("captured");
    expect(paystackEventCanAdvance(storedAttempt!, claimed)).toBe(false);
    expect((await db("storefront_paystack_webhook_inbox").where({ id: claimed.id }).first()).status).toBe("ignored");
  });

  test("continues durable inbox processing when the Firstout refund feed is unavailable", async () => {
    await db("storefront_paystack_payment_attempt").whereNull("deleted_at").update({ status: "captured" });
    await db("storefront_paystack_refund_dispatch").whereNull("deleted_at").update({ status: "succeeded" });
    await db("storefront_paystack_webhook_inbox").whereNull("deleted_at")
      .whereIn("status", ["received", "retry", "processing"])
      .update({ status: "ignored", lease_until: null, lease_token: null, next_attempt_at: null });
    const inbox = await receivePaystackObservation(db, { ...charge(`dk_job_${randomUUID().slice(0, 8)}`, "failed", new Date().toISOString()), kind: "other" as "charge" }, "status");
    const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response("unavailable", { status: 503 }));
    const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    try {
      await processPaystackWebhooksJob(dbContainer(), fetcher as typeof fetch);
    } finally {
      warn.mockRestore();
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(String(fetcher.mock.calls[0]?.[0])).toContain("refund-commands?limit=100");
    expect(await db("storefront_paystack_webhook_inbox").where({ id: inbox.id }).first()).toMatchObject({ status: "ignored" });
  });
});
