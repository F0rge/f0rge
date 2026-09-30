import { createHash, randomUUID } from "node:crypto";
import type { Knex } from "knex";
import type { PeachWebhookEvent } from "./peach-checkout";
import { peachResultState } from "./peach-checkout";

export const PEACH_ATTEMPTS_TABLE = "storefront_peach_payment_attempt";
export const PEACH_INBOX_TABLE = "storefront_peach_webhook_inbox";

export type PeachAttempt = {
  id: string;
  payment_session_id: string;
  merchant_reference: string;
  nonce: string;
  checkout_id: string | null;
  amount_minor: number;
  currency_code: string;
  status: string;
  redirect_url: string | null;
  last_event_timestamp: string | null;
  last_event_state: string | null;
  last_status_checked_at: Date | string | null;
};

export type PeachInboxEvent = PeachWebhookEvent & {
  id: string;
  event_key: string;
  source: "webhook" | "status";
  result_state: string;
  status: string;
  attempt_count: number;
  lease_until: Date | string | null;
  lease_token: string | null;
};

export function peachEventCanAdvance(attempt: Pick<PeachAttempt, "status" | "last_event_timestamp">,
  event: Pick<PeachInboxEvent, "event_timestamp" | "result_state">): boolean {
  const timestamp = Date.parse(event.event_timestamp);
  const previousTimestamp = attempt.last_event_timestamp ? Date.parse(attempt.last_event_timestamp) : Number.NaN;
  if (!Number.isFinite(timestamp) || (Number.isFinite(previousTimestamp) && timestamp < previousTimestamp)) return false;
  return attempt.status !== "captured" || event.result_state === "paid";
}

export async function findPeachAttemptBySession(db: Knex, sessionId: string): Promise<PeachAttempt | undefined> {
  return db<PeachAttempt>(PEACH_ATTEMPTS_TABLE).where({ payment_session_id: sessionId }).whereNull("deleted_at").first();
}

export async function findPeachAttemptByReference(db: Knex, merchantReference: string): Promise<PeachAttempt | undefined> {
  return db<PeachAttempt>(PEACH_ATTEMPTS_TABLE).where({ merchant_reference: merchantReference }).whereNull("deleted_at").first();
}

export async function findPeachAttemptByCheckoutId(db: Knex, checkoutId: string): Promise<PeachAttempt | undefined> {
  return db<PeachAttempt>(PEACH_ATTEMPTS_TABLE).where({ checkout_id: checkoutId }).whereNull("deleted_at").first();
}

export async function listPeachAttemptsForStatusCheck(db: Knex, limit = 50): Promise<PeachAttempt[]> {
  return db<PeachAttempt>(PEACH_ATTEMPTS_TABLE)
    .whereNull("deleted_at")
    .whereNotNull("checkout_id")
    .whereIn("status", ["checkout_created", "initiation_unknown", "pending", "unknown", "cancelled"])
    .where((query) => query.whereNull("last_status_checked_at")
      .orWhere("last_status_checked_at", "<", db.raw("NOW() - INTERVAL '1 minute'")))
    .orderBy("last_status_checked_at", "asc")
    .limit(Math.max(1, Math.min(limit, 100)));
}

export async function claimPeachAttemptStatusCheck(db: Knex, id: string): Promise<boolean> {
  const changed = await db(PEACH_ATTEMPTS_TABLE).where({ id }).whereNull("deleted_at").whereNotNull("checkout_id")
    .whereIn("status", ["checkout_created", "initiation_unknown", "pending", "unknown", "cancelled"])
    .where((query) => query.whereNull("last_status_checked_at")
      .orWhere("last_status_checked_at", "<", db.raw("NOW() - INTERVAL '1 minute'")))
    .update({ last_status_checked_at: db.raw("NOW()"), updated_at: db.raw("NOW()") });
  return changed > 0;
}

export async function createPeachAttempt(db: Knex, input: {
  paymentSessionId: string;
  amountMinor: number;
  currencyCode: string;
}): Promise<{ attempt: PeachAttempt; created: boolean }> {
  try {
    return await db.transaction(async (trx) => {
      const existing = await trx<PeachAttempt>(PEACH_ATTEMPTS_TABLE)
        .where({ payment_session_id: input.paymentSessionId }).whereNull("deleted_at").forUpdate().first();
      if (existing) {
        if (Number(existing.amount_minor) !== input.amountMinor || existing.currency_code !== input.currencyCode) {
          throw new Error("Peach payment session amount or currency changed after initiation");
        }
        return { attempt: existing, created: false };
      }
      const attempt: PeachAttempt = {
        id: `spay_${randomUUID().replaceAll("-", "")}`,
        payment_session_id: input.paymentSessionId,
        merchant_reference: randomUUID().replaceAll("-", "").slice(0, 16),
        nonce: randomUUID().replaceAll("-", ""),
        checkout_id: null,
        amount_minor: input.amountMinor,
        currency_code: input.currencyCode,
        status: "initiating",
        redirect_url: null,
        last_event_timestamp: null,
        last_event_state: null,
        last_status_checked_at: null,
      };
      const now = new Date();
      await trx(PEACH_ATTEMPTS_TABLE).insert({
        ...attempt, raw_amount_minor: { value: String(input.amountMinor), precision: 20 }, created_at: now, updated_at: now,
      });
      return { attempt, created: true };
    });
  } catch (error) {
    // A concurrent provider invocation can win the unique session constraint.
    const existing = await findPeachAttemptBySession(db, input.paymentSessionId);
    if (!existing) throw error;
    if (Number(existing.amount_minor) !== input.amountMinor || existing.currency_code !== input.currencyCode) {
      throw new Error("Peach payment session amount or currency changed after initiation");
    }
    return { attempt: existing, created: false };
  }
}

export async function updatePeachAttempt(db: Knex, id: string, values: Partial<Pick<PeachAttempt,
  "checkout_id" | "status" | "redirect_url" | "last_event_timestamp" | "last_event_state" | "last_status_checked_at">>): Promise<void> {
  await db(PEACH_ATTEMPTS_TABLE).where({ id }).whereNull("deleted_at").update({ ...values, updated_at: new Date() });
}

export async function receivePeachWebhook(db: Knex, event: PeachWebhookEvent, signature: string | null, source: "webhook" | "status" = "webhook"): Promise<{ id: string; duplicate: boolean }> {
  if (source === "webhook" && !event.webhook_id) throw new Error("Peach webhook ID is missing");
  const eventKey = source === "webhook" ? `webhook:${event.webhook_id}` : `status:${event.canonical_sha256}`;
  const signatureSha256 = signature === null ? null : createHash("sha256").update(signature).digest("hex");
  const now = new Date();
  const row = {
    id: `spwh_${randomUUID().replaceAll("-", "")}`,
    event_key: eventKey,
    source,
    webhook_id: event.webhook_id,
    checkout_id: event.checkout_id,
    merchant_reference: event.merchant_reference,
    amount_minor: event.amount_minor,
    raw_amount_minor: { value: String(event.amount_minor), precision: 20 },
    currency_code: event.currency_code,
    payment_type: event.payment_type,
    result_code: event.result_code,
    transaction_id: event.transaction_id,
    event_timestamp: event.event_timestamp,
    result_state: peachResultState(event.result_code, event.payment_type),
    raw_sha256: event.raw_sha256,
    canonical_sha256: event.canonical_sha256,
    signature_sha256: signatureSha256,
    status: "received",
    attempt_count: 0,
    next_attempt_at: null,
    lease_until: null,
    lease_token: null,
    last_error_code: null,
    processed_at: null,
    created_at: now,
    updated_at: now,
  };
  const inserted = await db(PEACH_INBOX_TABLE).insert(row)
    .onConflict(db.raw("(event_key) where deleted_at is null")).ignore().returning(["id"]);
  if (inserted.length > 0) return { id: row.id, duplicate: false };

  const existing = await db<PeachInboxEvent>(PEACH_INBOX_TABLE).where({ event_key: eventKey }).whereNull("deleted_at").first();
  if (!existing) throw new Error("Peach webhook could not be persisted");
  if (existing.canonical_sha256 !== event.canonical_sha256) {
    throw new Error("Peach reused a webhook ID for different payment data");
  }
  return { id: existing.id, duplicate: true };
}

/** Claims one inbox row atomically; concurrent workers skip rows already leased. */
export async function claimPeachWebhook(db: Knex, id?: string): Promise<PeachInboxEvent | undefined> {
  const now = new Date();
  const leaseToken = randomUUID();
  const due = id ? "id = ? AND " : "";
  const bindings = id ? [id, now, leaseToken] : [now, leaseToken];
  const result = await db.raw(
    `WITH candidate AS (
      SELECT id FROM ${PEACH_INBOX_TABLE}
      WHERE deleted_at IS NULL AND ${due}((status IN ('received', 'retry') AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
        OR (status = 'processing' AND lease_until < NOW()))
      ORDER BY created_at ASC
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    UPDATE ${PEACH_INBOX_TABLE} AS inbox
      SET status = 'processing', attempt_count = inbox.attempt_count + 1,
          lease_until = NOW() + INTERVAL '2 minutes', lease_token = ?, updated_at = NOW()
      FROM candidate WHERE inbox.id = candidate.id
      RETURNING inbox.*`,
    bindings,
  );
  return result.rows[0] as PeachInboxEvent | undefined;
}

export async function completePeachWebhook(db: Knex, id: string, leaseToken: string | null, status: "processed" | "ignored" | "paid_exception"): Promise<void> {
  if (!leaseToken) throw new Error("Peach webhook claim has no lease token");
  const changed = await db(PEACH_INBOX_TABLE).where({ id, status: "processing", lease_token: leaseToken }).whereNull("deleted_at").update({
    status, lease_until: null, lease_token: null, next_attempt_at: null, processed_at: new Date(), updated_at: new Date(),
  });
  if (!changed) throw new Error("Peach webhook claim expired before completion");
}

export async function retryPeachWebhook(db: Knex, id: string, leaseToken: string | null, errorCode: string): Promise<void> {
  if (!leaseToken) return;
  const changed = await db(PEACH_INBOX_TABLE).where({ id, status: "processing", lease_token: leaseToken }).whereNull("deleted_at").update({
    status: "retry", last_error_code: errorCode, lease_until: null, lease_token: null,
    next_attempt_at: db.raw("NOW() + LEAST(INTERVAL '1 hour', INTERVAL '15 seconds' * POWER(2, LEAST(attempt_count, 8)))"),
    updated_at: new Date(),
  });
  if (!changed) throw new Error("Peach webhook claim expired before retry was recorded");
}
