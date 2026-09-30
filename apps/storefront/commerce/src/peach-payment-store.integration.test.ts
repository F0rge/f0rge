import knexFactory, { type Knex } from "knex";
import { randomUUID } from "node:crypto";
import { ContainerRegistrationKeys, Modules, PaymentActions, PaymentSessionStatus } from "@medusajs/framework/utils";
import type { AuthorizePaymentInput, CapturePaymentInput, MedusaContainer, ProviderWebhookPayload } from "@medusajs/framework/types";
import {
  claimPeachWebhook, completePeachWebhook, createPeachAttempt, findPeachAttemptByReference,
  peachEventCanAdvance, receivePeachWebhook, updatePeachAttempt,
} from "./peach-payment-store";
import { processClaimedPeachWebhook } from "./peach-webhook-processing";
import { parsePeachWebhook } from "./peach-checkout";
import { StorefrontPeachPaymentProvider } from "./modules/storefront-peach-payment-provider/service";
import { Migration20260930180331 } from "./modules/storefront-peach/migrations/Migration20260930180331";

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

  beforeAll(async () => {
    admin = knexFactory({ client: "pg", connection: databaseUrl });
    schema = `peach_test_${randomUUID().replaceAll("-", "")}`;
    await admin.raw("CREATE SCHEMA ??", [schema]);
    db = knexFactory({ client: "pg", connection: databaseUrl, searchPath: [schema] });
    const migrationSql: string[] = [];
    const migrationCollector: Migration20260930180331 = Object.create(Migration20260930180331.prototype);
    Reflect.set(migrationCollector, "addSql", (statement: string) => migrationSql.push(statement));
    await migrationCollector.up();
    for (const statement of migrationSql) await db.raw(statement);
  });

  afterAll(async () => {
    if (db) await db.destroy();
    if (admin && schema) {
      await admin.raw("DROP SCHEMA ?? CASCADE", [schema]);
      await admin.destroy();
    }
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
    expect(action.action).toBe(PaymentActions.SUCCESSFUL);
    expect(peachEventCanAdvance({ ...attempt, status: "declined", last_event_timestamp: "2026-09-30T11:59:00Z" }, {
      event_timestamp: paidEvent.event_timestamp, result_state: "paid",
    })).toBe(true);

    await updatePeachAttempt(db, attempt.id, {
      status: "captured", last_event_timestamp: paidEvent.event_timestamp, last_event_state: "paid",
    });
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
});
