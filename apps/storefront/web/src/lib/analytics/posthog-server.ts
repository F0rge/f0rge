import { consentedAttribution } from "./attribution";
import { POSTHOG_CAPTURE_URL, type PostHogCapturePayload } from "./posthog-browser";
import { OutcomeLedger, planConfirmationOutcomes, planPaymentFailure, type PlannedServerOutcome } from "./outcomes";
import { analyticsEnvironment } from "./policy";
import type { PaymentProviderId } from "./commerce-events";

const sharedLedger = new OutcomeLedger();

export type ServerCaptureResult = "sent" | "skipped" | "duplicate" | "failed";

function transportProperties(properties: PostHogCapturePayload["properties"]): PostHogCapturePayload["properties"] {
  return { ...properties, $geoip_disable: true, environment: analyticsEnvironment() };
}

export async function captureServerOutcome(input: {
  consentHeader: string | null;
  customerTypeHeader?: string | null;
  planned: PlannedServerOutcome | null;
  projectToken?: string;
  fetcher?: typeof fetch;
  ledger?: OutcomeLedger;
}): Promise<ServerCaptureResult> {
  const attribution = consentedAttribution({
    get: (name) => name === "x-storefront-analytics-id"
      ? input.consentHeader
      : name === "x-storefront-customer-type"
        ? input.customerTypeHeader ?? null
        : null,
  });
  if (!attribution || !input.planned) return "skipped";
  const token = (input.projectToken ?? process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN ?? "").trim();
  if (!token) return "skipped";
  const ledger = input.ledger ?? sharedLedger;
  if (!ledger.claim(input.planned.insertId)) return "duplicate";
  const fetcher = input.fetcher || globalThis.fetch;
  const payload: PostHogCapturePayload = {
    api_key: token,
    event: input.planned.event.name,
    distinct_id: attribution.distinctId,
    properties: { ...transportProperties(input.planned.event.properties), $insert_id: input.planned.insertId },
  };
  try {
    const response = await fetcher(POSTHOG_CAPTURE_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(800),
    });
    if (!response.ok) {
      ledger.release(input.planned.insertId);
      return "failed";
    }
    return "sent";
  } catch {
    ledger.release(input.planned.insertId);
    return "failed";
  }
}

export async function publishConfirmationOutcomes(input: {
  headers: { get(name: string): string | null };
  cartId?: string | null;
  orderId?: string | null;
  payload: unknown;
  projectToken?: string;
  fetcher?: typeof fetch;
  ledger?: OutcomeLedger;
}): Promise<ServerCaptureResult[]> {
  const attribution = consentedAttribution(input.headers);
  if (!attribution) return [];
  const planned = planConfirmationOutcomes({
    cartId: input.cartId,
    orderId: input.orderId,
    customerType: attribution.customerType,
    payload: input.payload,
  });
  const results: ServerCaptureResult[] = [];
  for (const item of planned) {
    results.push(await captureServerOutcome({
      consentHeader: attribution.distinctId,
      customerTypeHeader: attribution.customerType,
      planned: item,
      projectToken: input.projectToken,
      fetcher: input.fetcher,
      ledger: input.ledger,
    }));
  }
  return results;
}

export async function publishPaymentFailure(input: {
  headers: { get(name: string): string | null };
  cartId: string | null;
  outcome: unknown;
  provider?: PaymentProviderId;
  projectToken?: string;
  fetcher?: typeof fetch;
  ledger?: OutcomeLedger;
}): Promise<ServerCaptureResult> {
  try {
    const attribution = consentedAttribution(input.headers);
    return await captureServerOutcome({
      consentHeader: attribution?.distinctId ?? null,
      customerTypeHeader: attribution?.customerType ?? null,
      planned: planPaymentFailure({ cartId: input.cartId, outcome: input.outcome, provider: input.provider }),
      projectToken: input.projectToken,
      fetcher: input.fetcher,
      ledger: input.ledger,
    });
  } catch {
    return "failed";
  }
}
