import { sanitizeAnalyticsEvent, type SanitizedAnalyticsEvent } from "./events";

export const CONSENTED_MEASUREMENT_SCOPE = "consented_visitors" as const;
export const CONSENTED_MEASUREMENT_DISCLAIMER =
  "Consented visitors are not a census. Totals and rates use only visitors who accepted optional analytics.";

export type ConsentedReportRow = Record<string, string | number | boolean>;
export type ConsentedReport = {
  title: string;
  scope: typeof CONSENTED_MEASUREMENT_SCOPE;
  disclaimer: string;
  denominators: "matching_consent_scope";
  rows: ConsentedReportRow[];
};

function countBy(events: SanitizedAnalyticsEvent[], name: SanitizedAnalyticsEvent["name"], key: string): ConsentedReportRow[] {
  const totals = new Map<string, number>();
  for (const event of events) {
    if (event.name !== name) continue;
    const value = event.properties[key];
    const label = typeof value === "string" || typeof value === "number" ? String(value) : "(none)";
    totals.set(label, (totals.get(label) || 0) + 1);
  }
  return [...totals.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([dimension, event_count]) => ({ [key]: dimension, event_count }));
}

function report(title: string, rows: ConsentedReportRow[]): ConsentedReport {
  return {
    title,
    scope: CONSENTED_MEASUREMENT_SCOPE,
    disclaimer: CONSENTED_MEASUREMENT_DISCLAIMER,
    denominators: "matching_consent_scope",
    rows,
  };
}

/** Initial merchant reports over allowlisted events. Never treat this as a visitor census. */
export function consentedBrowsingReports(events: unknown[]): {
  acquisition: ConsentedReport;
  product: ConsentedReport;
  search: ConsentedReport;
} {
  const safe = events.flatMap((event) => {
    const sanitized = sanitizeAnalyticsEvent(event);
    return sanitized ? [sanitized] : [];
  });
  return {
    acquisition: report("Accepted page views by page and campaign", safe.filter((event) => event.name === "storefront_page_viewed").map((event) => ({
      page_key: String(event.properties.page_key),
      utm_source: typeof event.properties.utm_source === "string" ? event.properties.utm_source : "(none)",
      utm_campaign: typeof event.properties.utm_campaign === "string" ? event.properties.utm_campaign : "(none)",
    }))),
    product: report("Product impressions, selections and attention", [
      ...countBy(safe, "storefront_product_impressed", "surface"),
      ...safe.filter((event) => event.name === "storefront_product_attention_summary").map((event) => ({
        product_id: String(event.properties.product_id),
        active_seconds: Number(event.properties.active_seconds),
      })),
    ]),
    search: report("Search and merchandising outcomes", safe.filter((event) => event.name === "storefront_search_results_viewed").map((event) => ({
      availability: String(event.properties.availability),
      sort_order: String(event.properties.sort_order),
      query_present: Boolean(event.properties.query_present),
      result_count: Number(event.properties.result_count),
    }))),
  };
}
