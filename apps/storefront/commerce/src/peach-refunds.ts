import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type { PeachPaymentConfig } from "./peach-payment-config";
import { majorToMinor, minorToMajor } from "./peach-checkout";

export const PEACH_REFUND_URL = "https://testapi.peachpayments.com/v1/checkout/refund";

export type PeachRefundObservation = {
  provider_refund_id: string;
  referenced_capture_id: string;
  amount_minor: number;
  currency_code: string;
  result_code: string;
  outcome: "succeeded" | "pending" | "failed" | "unknown";
  event_timestamp: string;
  canonical_sha256: string;
};

type JsonRecord = Record<string, unknown>;

/** Checkout V1 signs sorted parameter names and values with no separators. */
export function peachCheckoutSignature(params: Record<string, string>, secret: string): string {
  const message = Object.keys(params).sort().map((key) => `${key}${params[key]}`).join("");
  return createHmac("sha256", secret).update(message, "utf8").digest("hex");
}

function flattenCheckoutResponse(value: unknown, prefix = "", output: Record<string, string> = {}): Record<string, string> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  for (const [key, child] of Object.entries(value as JsonRecord)) {
    const normalizedKey = key.replaceAll("_", ".");
    const name = prefix ? `${prefix}.${normalizedKey}` : normalizedKey;
    if (child !== null && typeof child === "object" && !Array.isArray(child)) {
      if (!flattenCheckoutResponse(child, name, output)) return null;
    } else if (Array.isArray(child)) return null;
    else if (child === null || typeof child === "string" || typeof child === "number" || typeof child === "boolean") {
      if (Object.prototype.hasOwnProperty.call(output, name)) return null;
      output[name] = child === null || child === false ? "" : child === true ? "1" : String(child);
    } else return null;
  }
  return output;
}

function signedResponseMatches(body: JsonRecord, secret: string): boolean {
  const signature = typeof body.signature === "string" ? body.signature.toLowerCase() : "";
  if (!/^[a-f0-9]{64}$/.test(signature)) return false;
  const fields = flattenCheckoutResponse(body);
  if (!fields) return false;
  delete fields.signature;
  const expected = Buffer.from(peachCheckoutSignature(fields, secret), "hex");
  const received = Buffer.from(signature, "hex");
  return expected.length === received.length && timingSafeEqual(expected, received);
}

function nestedCode(body: JsonRecord): string | null {
  const result = body.result;
  if (!result || typeof result !== "object" || Array.isArray(result)) return null;
  const code = (result as JsonRecord).code;
  return typeof code === "string" && /^[A-Za-z0-9.]{1,32}$/.test(code) ? code : null;
}

export function peachRefundOutcome(code: string): PeachRefundObservation["outcome"] {
  if (code === "000.100.110" || /^000\.000\./.test(code)) return "succeeded";
  if (/^000\.200\./.test(code)) return "pending";
  // Known terminal declines from the Checkout refund response contract. Other
  // statuses remain unknown so an ambiguous result is never resent.
  if (["100.550.701", "700.400.200", "700.300.100"].includes(code)) return "failed";
  return "unknown";
}

/** Verify and normalize a classic Checkout refund response before it is trusted. */
export function parsePeachRefundResponse(
  body: unknown,
  secret: string,
  expected: { referencedCaptureId: string; amountMinor: number; currencyCode: string },
): PeachRefundObservation | null {
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  const value = body as JsonRecord;
  if (!signedResponseMatches(value, secret)) return null;
  const providerRefundId = typeof value.id === "string" ? value.id : "";
  const referenced = typeof value.referencedId === "string" ? value.referencedId : expected.referencedCaptureId;
  const amount = majorToMinor(value.amount);
  const currency = typeof value.currency === "string" ? value.currency.toUpperCase() : "";
  const paymentType = typeof value.paymentType === "string" ? value.paymentType : "";
  const resultCode = nestedCode(value);
  const timestamp = typeof value.timestamp === "string" && Number.isFinite(Date.parse(value.timestamp))
    ? new Date(value.timestamp).toISOString()
    : "";
  if (!/^[a-f0-9]{32}$/i.test(providerRefundId) || !/^[a-f0-9]{32}$/i.test(referenced) ||
    referenced.toLowerCase() !== expected.referencedCaptureId.toLowerCase() || amount !== expected.amountMinor ||
    currency !== expected.currencyCode.toUpperCase() || paymentType !== "RF" || !resultCode || !timestamp) return null;
  const normalized = {
    provider_refund_id: providerRefundId,
    referenced_capture_id: referenced,
    amount_minor: amount,
    currency_code: currency,
    result_code: resultCode,
    outcome: peachRefundOutcome(resultCode),
    event_timestamp: timestamp,
  };
  return { ...normalized, canonical_sha256: createHash("sha256").update(JSON.stringify(normalized)).digest("hex") };
}

export async function peachRefundPayment(
  config: PeachPaymentConfig,
  input: { referencedCaptureId: string; amountMinor: number; currencyCode: string },
  fetcher: typeof fetch = fetch,
): Promise<PeachRefundObservation | null> {
  if (!config.checkoutSecret) throw new Error("Peach Checkout signing secret is not configured");
  if (input.currencyCode.toUpperCase() !== "ZAR" || !Number.isSafeInteger(input.amountMinor) || input.amountMinor <= 0 ||
    !/^[a-f0-9]{32}$/i.test(input.referencedCaptureId)) {
    throw new Error("Peach refund command is invalid");
  }
  const params = {
    amount: minorToMajor(input.amountMinor).toFixed(2),
    "authentication.entityId": config.entityId,
    currency: input.currencyCode.toUpperCase(),
    id: input.referencedCaptureId,
    paymentType: "RF",
  };
  const signature = peachCheckoutSignature(params, config.checkoutSecret);
  const response = await fetcher(PEACH_REFUND_URL, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/json",
    },
    body: JSON.stringify({ ...params, signature }),
    signal: AbortSignal.timeout(15_000),
    cache: "no-store",
  });
  let body: unknown;
  try { body = await response.json(); }
  catch { return null; }
  // Transport/HTTP failure is not enough to prove a refund failed. The signed
  // body, not the HTTP status, supplies the payment outcome.
  return parsePeachRefundResponse(body, config.checkoutSecret, input);
}
