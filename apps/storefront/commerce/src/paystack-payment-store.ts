import { createHash, randomUUID } from "node:crypto";
import type { Knex } from "knex";
import { paystackChargeState, paystackRefundOutcome, type PaystackObservation } from "./paystack-checkout";

export const PAYSTACK_ATTEMPTS_TABLE = "storefront_paystack_payment_attempt";
export const PAYSTACK_INBOX_TABLE = "storefront_paystack_webhook_inbox";
export const PAYSTACK_REFUNDS_TABLE = "storefront_paystack_refund_dispatch";

export type PaystackAttempt = {
  id: string;
  payment_session_id: string;
  cart_id?: string | null;
  checkout_snapshot?: Record<string, unknown> | null;
  reference: string;
  transaction_id: string | null;
  captured_order_id: string | null;
  amount_minor: number;
  currency_code: string;
  status: string;
  authorization_url: string | null;
  last_event_timestamp: string | null;
  last_event_state: string | null;
  last_status_checked_at: Date | string | null;
};

export type PaystackInboxSource = "webhook" | "status" | "refund-response";

export type PaystackInboxEvent = PaystackObservation & {
  id: string;
  event_key: string;
  source: PaystackInboxSource;
  result_state: string;
  signature_sha256: string | null;
  status: string;
  attempt_count: number;
  lease_until: Date | string | null;
  lease_token: string | null;
};

export type PaystackRefundCommand = {
  request_id: string;
  handoff_id: string;
  external_order_id: string;
  /** Firstout's capture identity: our Paystack charge reference. */
  original_transaction_id: string;
  amount_minor: number;
  currency_code: string;
  cancel_order: boolean;
  allocation?: Record<string, unknown>;
  status: string;
};

export type PaystackRefundDispatch = {
  id: string;
  request_id: string;
  handoff_id: string | null;
  external_order_id: string;
  original_transaction_id: string;
  amount_minor: number;
  currency_code: string;
  cancel_order: boolean;
  allocation: Record<string, unknown>;
  status: string;
  firstout_status: string | null;
  provider_refund_id: string | null;
  provider_result_code: string | null;
  canonical_sha256: string | null;
  medusa_payment_id: string | null;
  medusa_refund_id: string | null;
  authorization_key: string | null;
};

const STATUS_CHECK_STATES = ["initiating", "checkout_created", "initiation_unknown", "pending", "unknown"];

export function paystackEventCanAdvance(attempt: Pick<PaystackAttempt, "status" | "last_event_timestamp">,
  event: Pick<PaystackInboxEvent, "event_timestamp" | "result_state">): boolean {
  const timestamp = Date.parse(event.event_timestamp);
  const previousTimestamp = attempt.last_event_timestamp ? Date.parse(attempt.last_event_timestamp) : Number.NaN;
  if (!Number.isFinite(timestamp) || (Number.isFinite(previousTimestamp) && timestamp < previousTimestamp)) return false;
  return attempt.status !== "captured" || event.result_state === "paid";
}

export async function findPaystackAttemptBySession(db: Knex, sessionId: string): Promise<PaystackAttempt | undefined> {
  return db<PaystackAttempt>(PAYSTACK_ATTEMPTS_TABLE).where({ payment_session_id: sessionId }).whereNull("deleted_at").first();
}

export async function findPaystackAttemptByReference(db: Knex, reference: string): Promise<PaystackAttempt | undefined> {
  return db<PaystackAttempt>(PAYSTACK_ATTEMPTS_TABLE).where({ reference }).whereNull("deleted_at").first();
}

export async function listPaystackAttemptsForStatusCheck(db: Knex, limit = 50): Promise<PaystackAttempt[]> {
  return db<PaystackAttempt>(PAYSTACK_ATTEMPTS_TABLE)
    .whereNull("deleted_at")
    .whereIn("status", STATUS_CHECK_STATES)
    .where((query) => query.whereNull("last_status_checked_at")
      .orWhere("last_status_checked_at", "<", db.raw("NOW() - INTERVAL '1 minute'")))
    .orderBy("last_status_checked_at", "asc")
    .limit(Math.max(1, Math.min(limit, 100)));
}

export async function claimPaystackAttemptStatusCheck(db: Knex, id: string): Promise<boolean> {
  const changed = await db(PAYSTACK_ATTEMPTS_TABLE).where({ id }).whereNull("deleted_at")
    .whereIn("status", STATUS_CHECK_STATES)
    .where((query) => query.whereNull("last_status_checked_at")
      .orWhere("last_status_checked_at", "<", db.raw("NOW() - INTERVAL '1 minute'")))
    .update({ last_status_checked_at: db.raw("NOW()"), updated_at: db.raw("NOW()") });
  return changed > 0;
}

export async function createPaystackAttempt(db: Knex, input: {
  paymentSessionId: string;
  cartId?: string | null;
  checkoutSnapshot?: Record<string, unknown> | null;
  amountMinor: number;
  currencyCode: string;
}): Promise<{ attempt: PaystackAttempt; created: boolean }> {
  try {
    return await db.transaction(async (trx) => {
      const existing = await trx<PaystackAttempt>(PAYSTACK_ATTEMPTS_TABLE)
        .where({ payment_session_id: input.paymentSessionId }).whereNull("deleted_at").forUpdate().first();
      if (existing) {
        if (Number(existing.amount_minor) !== input.amountMinor || existing.currency_code !== input.currencyCode) {
          throw new Error("Paystack payment session amount or currency changed after initiation");
        }
        return { attempt: existing, created: false };
      }
      const attempt: PaystackAttempt = {
        id: `spay_${randomUUID().replaceAll("-", "")}`,
        payment_session_id: input.paymentSessionId,
        cart_id: input.cartId || null,
        checkout_snapshot: input.checkoutSnapshot || null,
        reference: `dk_${randomUUID().replaceAll("-", "")}`,
        transaction_id: null,
        captured_order_id: null,
        amount_minor: input.amountMinor,
        currency_code: input.currencyCode,
        status: "initiating",
        authorization_url: null,
        last_event_timestamp: null,
        last_event_state: null,
        last_status_checked_at: null,
      };
      const now = new Date();
      await trx(PAYSTACK_ATTEMPTS_TABLE).insert({
        ...attempt, raw_amount_minor: { value: String(input.amountMinor), precision: 20 }, created_at: now, updated_at: now,
      });
      return { attempt, created: true };
    });
  } catch (error) {
    // A concurrent provider invocation can win the unique session constraint.
    const existing = await findPaystackAttemptBySession(db, input.paymentSessionId);
    if (!existing) throw error;
    if (Number(existing.amount_minor) !== input.amountMinor || existing.currency_code !== input.currencyCode) {
      throw new Error("Paystack payment session amount or currency changed after initiation");
    }
    return { attempt: existing, created: false };
  }
}

export async function updatePaystackAttempt(db: Knex, id: string, values: Partial<Pick<PaystackAttempt,
  "transaction_id" | "captured_order_id" | "status" | "authorization_url" | "last_event_timestamp" | "last_event_state" | "last_status_checked_at">>): Promise<void> {
  await db(PAYSTACK_ATTEMPTS_TABLE).where({ id }).whereNull("deleted_at").update({ ...values, updated_at: new Date() });
}

export function paystackResultState(event: Pick<PaystackObservation, "kind" | "provider_status">): string {
  return event.kind === "charge" ? paystackChargeState(event.provider_status) : paystackRefundOutcome(event.provider_status);
}

/** Paystack has no event ID and re-signs retries, so identical normalized facts are one inbox row. */
export async function receivePaystackObservation(
  db: Knex,
  event: PaystackObservation,
  source: PaystackInboxSource,
  signature: string | null = null,
  status: "received" | "needs_review" = "received",
): Promise<{ id: string; duplicate: boolean }> {
  const eventKey = `${event.kind}:${event.canonical_sha256}`;
  const now = new Date();
  const row = {
    id: `spwh_${randomUUID().replaceAll("-", "")}`,
    event_key: eventKey,
    source,
    kind: event.kind,
    reference: event.reference,
    transaction_id: event.transaction_id,
    provider_refund_id: event.provider_refund_id,
    refund_reference: event.refund_reference,
    refund_request_id: event.refund_request_id,
    amount_minor: event.amount_minor,
    raw_amount_minor: { value: String(event.amount_minor), precision: 20 },
    currency_code: event.currency_code,
    provider_status: event.provider_status,
    result_state: paystackResultState(event),
    event_timestamp: event.event_timestamp,
    raw_sha256: event.raw_sha256,
    canonical_sha256: event.canonical_sha256,
    signature_sha256: signature === null ? null : createHash("sha256").update(signature).digest("hex"),
    status,
    attempt_count: 0,
    next_attempt_at: null,
    lease_until: null,
    lease_token: null,
    last_error_code: null,
    processed_at: null,
    created_at: now,
    updated_at: now,
  };
  const inserted = await db(PAYSTACK_INBOX_TABLE).insert(row)
    .onConflict(db.raw("(event_key) where deleted_at is null")).ignore().returning(["id"]);
  if (inserted.length > 0) return { id: row.id, duplicate: false };
  const existing = await db<PaystackInboxEvent>(PAYSTACK_INBOX_TABLE).where({ event_key: eventKey }).whereNull("deleted_at").first();
  if (!existing) throw new Error("Paystack observation could not be persisted");
  return { id: existing.id, duplicate: true };
}

export async function findPaystackRefundDispatch(db: Knex, requestId: string): Promise<PaystackRefundDispatch | undefined> {
  return db<PaystackRefundDispatch>(PAYSTACK_REFUNDS_TABLE).where({ request_id: requestId }).whereNull("deleted_at").first();
}

export async function findPaystackRefundByProviderId(db: Knex, providerRefundId: string): Promise<PaystackRefundDispatch | undefined> {
  return db<PaystackRefundDispatch>(PAYSTACK_REFUNDS_TABLE).where({ provider_refund_id: providerRefundId }).whereNull("deleted_at").first();
}

export async function findPaystackRefundsForCapture(db: Knex, captureReference: string): Promise<PaystackRefundDispatch[]> {
  return db<PaystackRefundDispatch>(PAYSTACK_REFUNDS_TABLE).where({ original_transaction_id: captureReference }).whereNull("deleted_at");
}

/** Captures with a refund still waiting on Paystack, oldest first. */
export async function listPaystackCapturesWithOpenRefunds(db: Knex, limit = 25): Promise<string[]> {
  const rows = await db(PAYSTACK_REFUNDS_TABLE).whereNull("deleted_at")
    .whereIn("status", ["unknown", "pending", "needs_attention"])
    .groupBy("original_transaction_id").min("updated_at as oldest").select("original_transaction_id")
    .orderBy("oldest", "asc").limit(limit);
  return rows.map((row) => String(row.original_transaction_id));
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
    return `{${entries.map(([key, entry]) => `${JSON.stringify(key)}:${stableJson(entry)}`).join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function assertRefundCommandMatches(existing: PaystackRefundDispatch & { allocation?: unknown }, command: PaystackRefundCommand): void {
  if (Number(existing.amount_minor) !== command.amount_minor || existing.currency_code !== command.currency_code ||
    existing.original_transaction_id !== command.original_transaction_id || existing.external_order_id !== command.external_order_id ||
    existing.handoff_id !== (command.handoff_id || null) || existing.cancel_order !== command.cancel_order ||
    stableJson(existing.allocation || {}) !== stableJson(command.allocation || {})) {
    throw new Error("Paystack refund request changed after it was durably received");
  }
}

export async function createPaystackRefundDispatch(db: Knex, command: PaystackRefundCommand): Promise<{ dispatch: PaystackRefundDispatch; created: boolean }> {
  try {
    return await db.transaction(async (trx) => {
      const existing = await trx<PaystackRefundDispatch & { allocation?: unknown }>(PAYSTACK_REFUNDS_TABLE)
        .where({ request_id: command.request_id }).whereNull("deleted_at").forUpdate().first();
      if (existing) {
        assertRefundCommandMatches(existing, command);
        return { dispatch: existing, created: false };
      }
      const row: PaystackRefundDispatch = {
        id: `srefund_${randomUUID().replaceAll("-", "")}`,
        request_id: command.request_id,
        handoff_id: command.handoff_id || null,
        external_order_id: command.external_order_id,
        original_transaction_id: command.original_transaction_id,
        amount_minor: command.amount_minor,
        currency_code: command.currency_code,
        cancel_order: command.cancel_order,
        allocation: command.allocation || {},
        status: "received",
        firstout_status: null,
        provider_refund_id: null,
        provider_result_code: null,
        canonical_sha256: null,
        medusa_payment_id: null,
        medusa_refund_id: null,
        authorization_key: null,
      };
      const now = new Date();
      await trx(PAYSTACK_REFUNDS_TABLE).insert({
        ...row,
        raw_amount_minor: { value: String(command.amount_minor), precision: 20 },
        allocation: command.allocation || {},
        created_at: now,
        updated_at: now,
      });
      return { dispatch: row, created: true };
    });
  } catch (error) {
    // Two workers can both observe no row before either insert commits. The
    // unique request ID makes the loser converge on the durable winner.
    const existing = await db<PaystackRefundDispatch & { allocation?: unknown }>(PAYSTACK_REFUNDS_TABLE)
      .where({ request_id: command.request_id }).whereNull("deleted_at").first();
    if (!existing) throw error;
    assertRefundCommandMatches(existing, command);
    return { dispatch: existing, created: false };
  }
}

export async function updatePaystackRefundDispatch(
  db: Knex,
  requestId: string,
  values: Partial<Pick<PaystackRefundDispatch, "status" | "firstout_status" | "provider_refund_id" | "provider_result_code" | "canonical_sha256" | "medusa_payment_id" | "medusa_refund_id" | "authorization_key">>,
): Promise<void> {
  await db(PAYSTACK_REFUNDS_TABLE).where({ request_id: requestId }).whereNull("deleted_at")
    .update({ ...values, updated_at: new Date() });
}

/** Transition only unresolved local intents to unknown after a stale remote
 * dispatching observation. A concurrent verified result or completed Medusa
 * projection must win and must never be downgraded by an older feed snapshot. */
export async function markPaystackRefundDispatchUnknownIfUnresolved(db: Knex, requestId: string): Promise<boolean> {
  const changed = await db(PAYSTACK_REFUNDS_TABLE).where({ request_id: requestId }).whereNull("deleted_at")
    .whereIn("status", ["received", "dispatching"])
    .update({ status: "unknown", updated_at: new Date() });
  if (changed) return true;
  return (await findPaystackRefundDispatch(db, requestId))?.status === "unknown";
}

export async function claimPaystackRefundDispatchForDispatch(db: Knex, requestId: string): Promise<boolean> {
  const changed = await db(PAYSTACK_REFUNDS_TABLE).where({ request_id: requestId, status: "received" })
    .whereNull("deleted_at").update({ status: "dispatching", updated_at: new Date() });
  return changed > 0;
}

export async function claimPaystackRefundForMedusa(
  db: Knex,
  input: { requestId: string; providerRefundId: string; capability: string; paymentId: string; refundId: string; amountMinor: number },
): Promise<boolean> {
  const changed = await db(PAYSTACK_REFUNDS_TABLE).where({
    request_id: input.requestId,
    provider_refund_id: input.providerRefundId,
    status: "verified",
    authorization_key: input.capability,
    medusa_payment_id: input.paymentId,
  }).whereNull("deleted_at").whereNull("medusa_refund_id")
    .where("amount_minor", input.amountMinor)
    .update({ status: "recording_medusa_refund", medusa_refund_id: input.refundId, updated_at: new Date() });
  if (changed) return true;
  const existing = await findPaystackRefundDispatch(db, input.requestId);
  return existing?.provider_refund_id === input.providerRefundId && existing.medusa_refund_id === input.refundId && existing.medusa_payment_id === input.paymentId &&
    existing.authorization_key === input.capability && Number(existing.amount_minor) === input.amountMinor &&
    ["recording_medusa_refund", "succeeded"].includes(existing.status);
}

/** Claims one inbox row atomically; concurrent workers skip rows already leased. */
export async function claimPaystackObservation(db: Knex, id?: string): Promise<PaystackInboxEvent | undefined> {
  const now = new Date();
  const leaseToken = randomUUID();
  const due = id ? "id = ? AND " : "";
  const bindings = id ? [id, now, leaseToken] : [now, leaseToken];
  const result = await db.raw(
    `WITH candidate AS (
      SELECT id FROM ${PAYSTACK_INBOX_TABLE}
      WHERE deleted_at IS NULL AND ${due}((status IN ('received', 'retry') AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
        OR (status = 'processing' AND lease_until < NOW()))
      ORDER BY created_at ASC
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    UPDATE ${PAYSTACK_INBOX_TABLE} AS inbox
      SET status = 'processing', attempt_count = inbox.attempt_count + 1,
          lease_until = NOW() + INTERVAL '2 minutes', lease_token = ?, updated_at = NOW()
      FROM candidate WHERE inbox.id = candidate.id
      RETURNING inbox.*`,
    bindings,
  );
  return result.rows[0] as PaystackInboxEvent | undefined;
}

export async function completePaystackObservation(db: Knex, id: string, leaseToken: string | null, status: "processed" | "ignored" | "paid_exception" | "needs_review"): Promise<void> {
  if (!leaseToken) throw new Error("Paystack observation claim has no lease token");
  const changed = await db(PAYSTACK_INBOX_TABLE).where({ id, status: "processing", lease_token: leaseToken }).whereNull("deleted_at").update({
    status, lease_until: null, lease_token: null, next_attempt_at: null, processed_at: new Date(), updated_at: new Date(),
  });
  if (!changed) throw new Error("Paystack observation claim expired before completion");
}

export async function retryPaystackObservation(db: Knex, id: string, leaseToken: string | null, errorCode: string): Promise<void> {
  if (!leaseToken) return;
  const changed = await db(PAYSTACK_INBOX_TABLE).where({ id, status: "processing", lease_token: leaseToken }).whereNull("deleted_at").update({
    status: "retry", last_error_code: errorCode, lease_until: null, lease_token: null,
    next_attempt_at: db.raw("NOW() + LEAST(INTERVAL '1 hour', INTERVAL '15 seconds' * POWER(2, LEAST(attempt_count, 8)))"),
    updated_at: new Date(),
  });
  if (!changed) throw new Error("Paystack observation claim expired before retry was recorded");
}
