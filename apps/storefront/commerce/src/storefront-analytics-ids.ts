import { createHash } from "node:crypto";

const OPAQUE_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const REFUND_ID_PREFIX = "storefront-refund:v1:";

function opaqueAnalyticsId(value: unknown): string | null {
  if (typeof value !== "string" || !OPAQUE_ID.test(value) || /^(phc_|phx_)/i.test(value)) return null;
  return value;
}

/** Stable order id shared by cart confirmation and email confirmation. */
export function storefrontAnalyticsOrderId(value: unknown): string | null {
  return opaqueAnalyticsId(value);
}

/** Hash of a stable refund field. The raw provider token is not returned. */
export function storefrontAnalyticsRefundId(refund: { medusa_refund_id?: unknown; provider_refund_id?: unknown }): string | null {
  const medusa = typeof refund.medusa_refund_id === "string" ? refund.medusa_refund_id : "";
  const provider = typeof refund.provider_refund_id === "string" ? refund.provider_refund_id : "";
  const source = medusa || provider;
  if (!source || source.length > 200) return null;
  const digest = createHash("sha256").update(`${REFUND_ID_PREFIX}${source}`).digest("hex").slice(0, 32);
  const id = `rf_${digest}`;
  if (source.length >= 4 && id.includes(source)) return null;
  return opaqueAnalyticsId(id);
}

export function storefrontCustomerRefund(item: Record<string, unknown>): {
  amount_minor: number;
  currency_code: unknown;
  status: unknown;
  analytics_refund_id?: string;
} {
  const analyticsRefundId = storefrontAnalyticsRefundId(item);
  return {
    amount_minor: Number(item.amount_minor),
    currency_code: item.currency_code,
    status: item.status,
    ...(analyticsRefundId ? { analytics_refund_id: analyticsRefundId } : {}),
  };
}
