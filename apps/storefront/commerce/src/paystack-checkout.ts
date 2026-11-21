import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { PAYSTACK_API_URL, type PaystackPaymentConfig } from "./paystack-payment-config";

/** One normalized, PII-free fact read from Paystack's authenticated API. */
export type PaystackObservation = {
  kind: "charge" | "refund";
  /** Our charge reference; for refunds, the refunded transaction's reference. */
  reference: string;
  /** Paystack's numeric charge ID, as text. */
  transaction_id: string | null;
  provider_refund_id: string | null;
  refund_reference: string | null;
  refund_request_id: string | null;
  amount_minor: number;
  currency_code: string;
  provider_status: string;
  event_timestamp: string;
  raw_sha256: string;
  canonical_sha256: string;
};

export type PaystackChargeState = "paid" | "pending" | "declined" | "unknown";
export type PaystackRefundOutcome = "succeeded" | "pending" | "failed" | "unknown";

const REFERENCE = /^[A-Za-z0-9_-]{8,64}$/;
const SIGNATURE_TOLERANCE_SECONDS = 300;

export function majorToMinor(value: unknown): number | null {
  const source = typeof value === "string" ? value : typeof value === "number" ? String(value) : "";
  const canonical = source.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  if (!/^(?:0|[1-9]\d{0,7})(?:\.\d{1,2})?$/.test(canonical)) return null;
  const [whole, fraction = ""] = canonical.split(".");
  const minor = Number(whole) * 100 + Number((fraction + "00").slice(0, 2));
  return Number.isSafeInteger(minor) ? minor : null;
}

export function medusaAmountToMinor(value: unknown): number | null {
  if (typeof value === "number") return majorToMinor(value);
  if (typeof value === "string") return majorToMinor(value);
  if (!value || typeof value !== "object") return null;
  const amount = value as { raw?: { value?: unknown }; value?: unknown; numeric?: unknown; numeric_?: unknown; toString?: () => string };
  const rawValue = amount.raw?.value;
  if (typeof rawValue === "number" || typeof rawValue === "string") return majorToMinor(rawValue);
  // MikroORM serializes Medusa's raw big-number column directly as
  // { value, precision }; the hydrated BigNumber instance instead exposes
  // that object under `.raw`. Both values are expressed in major currency
  // units, so normalize them identically.
  if (typeof amount.value === "number" || typeof amount.value === "string") return majorToMinor(amount.value);
  if (typeof amount.numeric === "number" || typeof amount.numeric === "string") return majorToMinor(amount.numeric);
  if (typeof amount.numeric_ === "number" || typeof amount.numeric_ === "string") return majorToMinor(amount.numeric_);
  if (typeof amount.toString === "function") return majorToMinor(amount.toString());
  return null;
}

export function minorToMajor(minor: number): number {
  return Number((minor / 100).toFixed(2));
}

/** Paystack amounts are already integer subunits (cents for ZAR). */
function subunitAmount(value: unknown): number | null {
  const amount = typeof value === "number" ? value : typeof value === "string" && /^\d{1,15}$/.test(value) ? Number(value) : NaN;
  return Number.isSafeInteger(amount) && amount >= 0 ? amount : null;
}

function providerId(value: unknown): string | null {
  const text = typeof value === "number" && Number.isSafeInteger(value) ? String(value) : typeof value === "string" ? value : "";
  return /^[A-Za-z0-9_-]{1,64}$/.test(text) ? text : null;
}

function timestamp(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && Number.isFinite(Date.parse(value))) return new Date(value).toISOString();
  }
  return null;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function isPaystackReference(value: unknown): value is string {
  return typeof value === "string" && REFERENCE.test(value);
}

/** Our refund reference is derived from Firstout's request ID, so a retried POST can never create a second refund. */
export function paystackRefundReference(requestId: string): string {
  const compact = requestId.replaceAll("-", "").toLowerCase();
  if (!/^[a-f0-9]{1,58}$/.test(compact)) throw new Error("refund_request_id_invalid");
  return `dkr_${compact}`;
}

/**
 * Verifies `Paystack-Signature: t=<unix>,v1=<kid>:<hex>[,v1=...]` over `${t}.${rawBody}`
 * with the whsec_ signing secret. Rejects timestamps outside a 300 second window.
 */
export function verifyPaystackWebhookSignature(input: {
  secret: string;
  header: string | undefined;
  rawBody: Buffer | undefined;
  nowSeconds?: number;
}): boolean {
  const { secret, header, rawBody } = input;
  if (!secret || typeof header !== "string" || !Buffer.isBuffer(rawBody)) return false;
  let t: number | null = null;
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const separator = part.indexOf("=");
    if (separator === -1) continue;
    const key = part.slice(0, separator).trim();
    const value = part.slice(separator + 1).trim();
    if (key === "t") {
      if (t !== null || !/^\d{1,12}$/.test(value)) return false;
      t = Number(value);
    } else if (key === "v1") {
      const kid = value.indexOf(":");
      if (kid !== -1) signatures.push(value.slice(kid + 1));
    }
  }
  const now = input.nowSeconds ?? Math.floor(Date.now() / 1000);
  if (t === null || !signatures.length || Math.abs(now - t) > SIGNATURE_TOLERANCE_SECONDS) return false;
  const expected = createHmac("sha512", secret).update(`${t}.`).update(rawBody).digest();
  return signatures.some((hex) => /^[0-9a-f]{128}$/.test(hex) &&
    timingSafeEqual(expected, Buffer.from(hex, "hex")));
}

export type PaystackWebhookTrigger =
  | { event: "charge.success"; reference: string }
  | { event: "refund"; reference: string }
  | { event: "ignored" };

/** A signed webhook is only a trigger; the processor re-reads the authoritative state from the API. */
export function parsePaystackWebhook(rawBody: Buffer): PaystackWebhookTrigger | null {
  let body: Record<string, unknown>;
  try { body = record(JSON.parse(rawBody.toString("utf8"))); }
  catch { return null; }
  const event = typeof body.event === "string" ? body.event : "";
  const data = record(body.data);
  if (event === "charge.success") {
    return isPaystackReference(data.reference) ? { event, reference: data.reference } : null;
  }
  if (event.startsWith("refund.")) {
    return isPaystackReference(data.transaction_reference) ? { event: "refund", reference: data.transaction_reference } : null;
  }
  return event ? { event: "ignored" } : null;
}

export function paystackChargeState(status: unknown): PaystackChargeState {
  if (status === "success") return "paid";
  if (status === "failed") return "declined";
  // Abandoned means the customer has not finished; they can still complete
  // the same hosted transaction, so it must not release the payment hold.
  if (["abandoned", "ongoing", "pending", "processing", "queued"].includes(String(status))) return "pending";
  // Reversed (refund or chargeback) and anything new needs a person.
  return "unknown";
}

export function paystackRefundOutcome(status: unknown): PaystackRefundOutcome {
  if (status === "processed") return "succeeded";
  if (status === "pending" || status === "processing") return "pending";
  if (status === "failed") return "failed";
  // needs-attention requires the customer's bank details. It is surfaced to
  // staff for a human to complete in the Paystack dashboard, never automated.
  return "unknown";
}

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

/** Normalize GET /transaction/verify/:reference without retaining customer or card fields. */
export function parsePaystackVerifyResponse(body: unknown, expectedReference: string): PaystackObservation | null {
  const envelope = record(body);
  const data = record(envelope.data);
  const amount = subunitAmount(data.amount);
  const currency = typeof data.currency === "string" ? data.currency.toUpperCase() : "";
  const status = typeof data.status === "string" ? data.status : "";
  const transactionId = providerId(data.id);
  const observedAt = timestamp(data.paid_at, data.paidAt, data.created_at, data.createdAt);
  if (envelope.status !== true || data.reference !== expectedReference || amount === null ||
    !/^[A-Z]{3}$/.test(currency) || !/^[a-z-]{1,32}$/.test(status) || !observedAt) return null;
  const normalized = {
    kind: "charge" as const, reference: expectedReference, transaction_id: transactionId,
    amount_minor: amount, currency_code: currency, provider_status: status,
  };
  return {
    ...normalized,
    provider_refund_id: null, refund_reference: null, refund_request_id: null,
    // Paid-at for a success is never older than the transaction's creation,
    // so a stale pending read cannot be ordered after the success.
    event_timestamp: status === "success" ? observedAt : timestamp(data.created_at, data.createdAt) || observedAt,
    raw_sha256: digest(body),
    canonical_sha256: digest(normalized),
  };
}

/** Normalize a refund object from POST /refund or GET /refund. */
export function parsePaystackRefund(
  value: unknown,
  expected: { reference: string; transactionId: string | null; refundRequestId: string | null; refundReference?: string | null },
): PaystackObservation | null {
  const data = record(value);
  const transaction = data.transaction && typeof data.transaction === "object" ? record(data.transaction) : null;
  const transactionId = providerId(transaction ? transaction.id : data.transaction);
  const transactionReference = transaction ? transaction.reference : undefined;
  const amount = subunitAmount(data.amount);
  const currency = typeof data.currency === "string" ? data.currency.toUpperCase() : "";
  const status = typeof data.status === "string" ? data.status : "";
  const refundId = providerId(data.id);
  const refundReference = typeof data.reference === "string" && REFERENCE.test(data.reference) ? data.reference : null;
  const observedAt = timestamp(data.created_at, data.createdAt, data.updated_at, data.updatedAt);
  if (!refundId || amount === null || amount <= 0 || !/^[A-Z]{3}$/.test(currency) || !/^[a-z-]{1,32}$/.test(status) ||
    !observedAt || (transactionReference !== undefined && transactionReference !== expected.reference) ||
    (expected.transactionId && transactionId !== expected.transactionId) ||
    // Without either charge identity, only our own unique refund reference binds the refund to the charge.
    (!expected.transactionId && transactionReference === undefined &&
      (!expected.refundReference || refundReference?.toLowerCase() !== expected.refundReference.toLowerCase()))) return null;
  const normalized = {
    kind: "refund" as const, reference: expected.reference, transaction_id: transactionId,
    provider_refund_id: refundId, refund_reference: refundReference,
    amount_minor: amount, currency_code: currency, provider_status: status,
  };
  return {
    ...normalized,
    refund_request_id: expected.refundRequestId,
    event_timestamp: observedAt,
    raw_sha256: digest(value),
    canonical_sha256: digest(normalized),
  };
}

async function paystackFetch(config: PaystackPaymentConfig, path: string, init: RequestInit = {}, fetcher: typeof fetch = fetch): Promise<Response> {
  return fetcher(`${PAYSTACK_API_URL}${path}`, {
    ...init,
    headers: {
      accept: "application/json",
      authorization: `Bearer ${config.secretKey}`,
      ...(init.body ? { "content-type": "application/json" } : {}),
    },
    signal: AbortSignal.timeout(15_000),
    cache: "no-store",
  });
}

export async function initializePaystackTransaction(
  config: PaystackPaymentConfig,
  input: { email: string; amountMinor: number; currencyCode: string; reference: string; metadata: Record<string, string> },
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  return paystackFetch(config, "/transaction/initialize", {
    method: "POST",
    body: JSON.stringify({
      email: input.email,
      amount: input.amountMinor,
      currency: input.currencyCode,
      reference: input.reference,
      callback_url: config.callbackUrl,
      metadata: input.metadata,
    }),
  }, fetcher);
}

/** Returns null when Paystack has no transaction with this reference. Throws on transport failure. */
export async function verifyPaystackTransaction(
  config: PaystackPaymentConfig,
  reference: string,
  fetcher: typeof fetch = fetch,
): Promise<PaystackObservation | null> {
  const response = await paystackFetch(config, `/transaction/verify/${encodeURIComponent(reference)}`, {}, fetcher);
  if (response.status === 400 || response.status === 404) return null;
  if (!response.ok) throw new Error(`paystack_verify_http_${response.status}`);
  const observation = parsePaystackVerifyResponse(await response.json(), reference);
  if (!observation) throw new Error("paystack_verify_response_invalid");
  return observation;
}

export type PaystackRefundRequestResult =
  | { kind: "observed"; observation: PaystackObservation }
  | { kind: "duplicate" }
  | { kind: "rejected"; status: number }
  | { kind: "ambiguous"; code: string };

export async function createPaystackRefund(
  config: PaystackPaymentConfig,
  input: { transactionReference: string; transactionId: string | null; amountMinor: number; currencyCode: string; requestId: string },
  fetcher: typeof fetch = fetch,
): Promise<PaystackRefundRequestResult> {
  if (input.currencyCode !== "ZAR" || !Number.isSafeInteger(input.amountMinor) || input.amountMinor <= 0 ||
    !isPaystackReference(input.transactionReference)) throw new Error("paystack_refund_command_invalid");
  let response: Response;
  try {
    response = await paystackFetch(config, "/refund", {
      method: "POST",
      body: JSON.stringify({
        transaction: input.transactionReference,
        amount: input.amountMinor,
        currency: input.currencyCode,
        reference: paystackRefundReference(input.requestId),
      }),
    }, fetcher);
  } catch {
    return { kind: "ambiguous", code: "paystack_refund_transport_failed" };
  }
  if (response.status === 409) return { kind: "duplicate" };
  if (response.status >= 500 || response.status === 429) return { kind: "ambiguous", code: `paystack_refund_http_${response.status}` };
  if (!response.ok) return { kind: "rejected", status: response.status };
  let body: Record<string, unknown>;
  try { body = record(await response.json()); }
  catch { return { kind: "ambiguous", code: "paystack_refund_response_unreadable" }; }
  const observation = body.status === true ? parsePaystackRefund(body.data, {
    reference: input.transactionReference, transactionId: input.transactionId, refundRequestId: input.requestId,
  }) : null;
  if (!observation || observation.refund_reference?.toLowerCase() !== paystackRefundReference(input.requestId) ||
    observation.amount_minor !== input.amountMinor || observation.currency_code !== input.currencyCode) {
    return { kind: "ambiguous", code: "paystack_refund_response_unverified" };
  }
  return { kind: "observed", observation };
}

/** Lists the refunds Paystack holds for one charge (by Paystack's numeric transaction ID). */
export async function listPaystackRefunds(
  config: PaystackPaymentConfig,
  query: { transactionId: string } | { refundReference: string },
  fetcher: typeof fetch = fetch,
): Promise<Record<string, unknown>[]> {
  const params = "transactionId" in query
    ? `transaction=${encodeURIComponent(query.transactionId)}&perPage=100`
    : `reference=${encodeURIComponent(query.refundReference)}`;
  const response = await paystackFetch(config, `/refund?${params}`, {}, fetcher);
  if (!response.ok) throw new Error(`paystack_refund_list_http_${response.status}`);
  const body = record(await response.json());
  if (body.status !== true || !Array.isArray(body.data)) throw new Error("paystack_refund_list_invalid");
  return body.data.map(record);
}
