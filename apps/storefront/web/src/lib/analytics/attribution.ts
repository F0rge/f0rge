export const ANALYTICS_ID_HEADER = "x-storefront-analytics-id";
export const ANALYTICS_CUSTOMER_TYPE_HEADER = "x-storefront-customer-type";

export type AnalyticsCustomerType = "guest" | "new" | "returning";

const customerTypes = new Set<AnalyticsCustomerType>(["guest", "new", "returning"]);

/** Opaque analytics id. Emails, secrets, and free text never qualify. */
export function opaqueAnalyticsId(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64) return null;
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value)) return null;
  if (/^(phc_|phx_)/i.test(value)) return null;
  return value;
}

export function analyticsCustomerType(value: unknown): AnalyticsCustomerType | null {
  return typeof value === "string" && customerTypes.has(value as AnalyticsCustomerType)
    ? value as AnalyticsCustomerType
    : null;
}

export function consentedAttribution(headers: { get(name: string): string | null }): {
  distinctId: string;
  customerType: AnalyticsCustomerType | null;
} | null {
  const distinctId = opaqueAnalyticsId(headers.get(ANALYTICS_ID_HEADER));
  if (!distinctId) return null;
  return { distinctId, customerType: analyticsCustomerType(headers.get(ANALYTICS_CUSTOMER_TYPE_HEADER)) };
}
