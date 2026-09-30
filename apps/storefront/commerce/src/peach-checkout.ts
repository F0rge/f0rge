import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type { PeachPaymentConfig } from "./peach-payment-config";

export type PeachWebhookEvent = {
  webhook_id: string | null;
  checkout_id: string;
  merchant_reference: string;
  amount_minor: number;
  currency_code: string;
  payment_type: string;
  result_code: string;
  transaction_id: string | null;
  event_timestamp: string;
  raw_sha256: string;
  canonical_sha256: string;
};

export type PeachResultState = "paid" | "pending" | "cancelled" | "declined" | "unknown";

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
  const amount = value as { raw?: { value?: unknown }; numeric?: unknown; numeric_?: unknown; toString?: () => string };
  const rawValue = amount.raw?.value;
  if (typeof rawValue === "number" || typeof rawValue === "string") return majorToMinor(rawValue);
  if (typeof amount.numeric === "number" || typeof amount.numeric === "string") return majorToMinor(amount.numeric);
  if (typeof amount.numeric_ === "number" || typeof amount.numeric_ === "string") return majorToMinor(amount.numeric_);
  if (typeof amount.toString === "function") return majorToMinor(amount.toString());
  return null;
}

export function minorToMajor(minor: number): number {
  return Number((minor / 100).toFixed(2));
}

export function verifyPeachWebhookSignature(input: {
  secret: string;
  configuredUrl: string;
  timestamp: string | undefined;
  webhookId: string | undefined;
  signature: string | undefined;
  algorithm: string | undefined;
  rawBody: Buffer | string | undefined;
}): boolean {
  const { secret, configuredUrl, timestamp, webhookId, signature, algorithm, rawBody } = input;
  const normalizedAlgorithm = algorithm?.toLowerCase().replaceAll("-", "");
  if (!secret || !timestamp || !webhookId || !signature || rawBody === undefined || rawBody === null ||
    normalizedAlgorithm !== "hmacsha256" || !/^[a-f\d]{64}$/i.test(signature)) return false;
  const message = `${timestamp}.${webhookId}.${configuredUrl}.${Buffer.isBuffer(rawBody) ? rawBody.toString("utf8") : rawBody}`;
  const expected = createHmac("sha256", secret).update(message).digest();
  const received = Buffer.from(signature, "hex");
  return expected.length === received.length && timingSafeEqual(expected, received);
}

export function parsePeachWebhook(rawBody: Buffer | string, webhookId: string): PeachWebhookEvent | null {
  const raw = Buffer.isBuffer(rawBody) ? rawBody.toString("utf8") : rawBody;
  const params = new URLSearchParams(raw);
  const one = (key: string): string | null => {
    const values = params.getAll(key);
    return values.length === 1 ? values[0] : null;
  };
  const checkoutId = one("checkoutId");
  const merchantReference = one("merchantTransactionId");
  const amount = one("amount");
  const currency = one("currency");
  const paymentType = one("paymentType");
  const dottedResultCodes = params.getAll("result.code");
  const underscoredResultCodes = params.getAll("result_code");
  if (dottedResultCodes.length > 1 || underscoredResultCodes.length > 1) return null;
  const dottedResultCode = dottedResultCodes[0] ?? null;
  const underscoredResultCode = underscoredResultCodes[0] ?? null;
  if (dottedResultCode && underscoredResultCode && dottedResultCode !== underscoredResultCode) return null;
  const resultCode = dottedResultCode ?? underscoredResultCode;
  const timestamp = one("timestamp");
  const transactionId = one("id");
  const amountMinor = majorToMinor(amount);
  if (!webhookId || webhookId.length > 200 || !checkoutId || !/^[A-Za-z0-9_-]{1,64}$/.test(checkoutId) ||
    !merchantReference || !/^[A-Za-z0-9]{8,16}$/.test(merchantReference) || amountMinor === null ||
    !currency || !/^[A-Za-z]{3}$/.test(currency) || !paymentType || !resultCode || resultCode.length > 32 ||
    !timestamp || !Number.isFinite(Date.parse(timestamp))) return null;
  const normalized = {
    webhook_id: webhookId,
    checkout_id: checkoutId,
    merchant_reference: merchantReference,
    amount_minor: amountMinor,
    currency_code: currency.toUpperCase(),
    payment_type: paymentType.toUpperCase(),
    result_code: resultCode,
    transaction_id: transactionId && transactionId.length <= 128 ? transactionId : null,
    event_timestamp: timestamp,
  };
  return {
    ...normalized,
    raw_sha256: createHash("sha256").update(Buffer.isBuffer(rawBody) ? rawBody : raw).digest("hex"),
    canonical_sha256: createHash("sha256").update(JSON.stringify(normalized)).digest("hex"),
  };
}

export function peachResultState(resultCode: unknown, paymentType: unknown): PeachResultState {
  if (paymentType !== "DB" || typeof resultCode !== "string") return "unknown";
  // These groupings and actions are published by Peach's response-code guide.
  // The successful-but-flagged-for-review 000.400.0xx group is intentionally
  // excluded because it requires human review before fulfillment.
  if (/^(000\.000\.|000\.100\.1|000\.[36]|000\.400\.1[12]0)/.test(resultCode) ||
    ["000.500.000", "000.500.100"].includes(resultCode)) return "paid";
  if (/^(000\.200\.|100\.400\.500|800\.400\.5)/.test(resultCode) || ["800.700.100", "800.600.100"].includes(resultCode)) return "pending";
  if (resultCode === "100.396.101") return "cancelled";
  if (resultCode === "100.396.104") return "unknown";
  // Peach documents these groups as rejected. Communication/system errors
  // remain unknown so they do not release a payment hold or trigger a retry.
  if (/^(?:000\.400\.(?:1[0-9][1-9]|2[0-9]{2})|800\.(?:100|700)\.|800\.800\.[123])/.test(resultCode)) return "declined";
  return "unknown";
}

export async function peachAccessToken(config: PeachPaymentConfig, fetcher: typeof fetch = fetch): Promise<{ token: string; expiresIn: number }> {
  const response = await fetcher(`${config.authBaseUrl}/api/oauth/token`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ clientId: config.clientId, clientSecret: config.clientSecret, merchantId: config.merchantId }),
    signal: AbortSignal.timeout(10_000),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Peach authentication is temporarily unavailable");
  const body = await response.json() as { access_token?: unknown; expires_in?: unknown };
  if (typeof body.access_token !== "string" || !body.access_token || typeof body.expires_in !== "number") {
    throw new Error("Peach authentication returned an invalid response");
  }
  return { token: body.access_token, expiresIn: body.expires_in };
}

export async function peachCheckoutStatus(config: PeachPaymentConfig, checkoutId: string, token: string, fetcher: typeof fetch = fetch): Promise<Record<string, unknown>> {
  const response = await fetcher(`${config.checkoutBaseUrl}/v2/checkout/${encodeURIComponent(checkoutId)}/status`, {
    headers: { accept: "application/json", authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10_000),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Peach payment status is temporarily unavailable");
  const body = await response.json() as Record<string, unknown>;
  return body;
}

export function peachCheckoutStatusFields(body: Record<string, unknown>): {
  resultCode: string | null;
  paymentType: string | null;
  checkoutId: string | null;
  merchantReference: string | null;
  amountMinor: number | null;
  currencyCode: string | null;
  transactionId: string | null;
  eventTimestamp: string | null;
} {
  const result = body.result && typeof body.result === "object" ? body.result as Record<string, unknown> : {};
  const nestedResultCode = typeof result.code === "string" ? result.code : null;
  const dottedResultCode = typeof body["result.code"] === "string" ? body["result.code"] as string : null;
  const resultCode = nestedResultCode && dottedResultCode && nestedResultCode !== dottedResultCode
    ? null : dottedResultCode || nestedResultCode;
  const paymentType = typeof body.paymentType === "string" ? body.paymentType : null;
  const checkoutId = typeof body.checkoutId === "string" ? body.checkoutId : null;
  const merchantReference = typeof body.merchantTransactionId === "string" ? body.merchantTransactionId : null;
  return {
    resultCode,
    paymentType,
    checkoutId,
    merchantReference,
    amountMinor: majorToMinor(body.amount),
    currencyCode: typeof body.currency === "string" ? body.currency.toUpperCase() : null,
    transactionId: typeof body.id === "string" && body.id.length <= 128 ? body.id : null,
    eventTimestamp: typeof body.timestamp === "string" && Number.isFinite(Date.parse(body.timestamp)) ? body.timestamp : null,
  };
}

/** Normalize Peach's bearer-authenticated V2 status response without retaining its PII fields. */
export function parsePeachStatusResponse(body: Record<string, unknown>): PeachWebhookEvent | null {
  const fields = peachCheckoutStatusFields(body);
  if (!fields.resultCode || fields.resultCode.length > 32 || !fields.checkoutId ||
    !/^[A-Za-z0-9._-]{1,64}$/.test(fields.checkoutId) || !fields.merchantReference ||
    !/^[A-Za-z0-9]{8,16}$/.test(fields.merchantReference) || fields.amountMinor === null ||
    !fields.currencyCode || !/^[A-Z]{3}$/.test(fields.currencyCode) || !fields.paymentType ||
    !/^[A-Z]{2}$/.test(fields.paymentType) || !fields.eventTimestamp) return null;
  const normalized = {
    webhook_id: null,
    checkout_id: fields.checkoutId,
    merchant_reference: fields.merchantReference,
    amount_minor: fields.amountMinor,
    currency_code: fields.currencyCode,
    payment_type: fields.paymentType,
    result_code: fields.resultCode,
    transaction_id: fields.transactionId,
    event_timestamp: fields.eventTimestamp,
  };
  return {
    ...normalized,
    raw_sha256: createHash("sha256").update(JSON.stringify(body)).digest("hex"),
    canonical_sha256: createHash("sha256").update(JSON.stringify(normalized)).digest("hex"),
  };
}
