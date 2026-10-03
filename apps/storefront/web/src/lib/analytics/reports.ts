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

function label(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "(none)";
}

function groupedRows(
  events: SanitizedAnalyticsEvent[],
  name: SanitizedAnalyticsEvent["name"],
  dimensions: string[],
  metric: "event_count" | "active_seconds" | "result_count",
): ConsentedReportRow[] {
  const totals = new Map<string, ConsentedReportRow>();
  for (const event of events) {
    if (event.name !== name) continue;
    const row: ConsentedReportRow = {};
    for (const dimension of dimensions) {
      if (dimension === "query_present") row[dimension] = event.properties[dimension] === true;
      else row[dimension] = label(event.properties[dimension]);
    }
    const key = JSON.stringify(row);
    const current = totals.get(key) || { ...row, [metric]: 0 };
    const increment = metric === "event_count" ? 1 : Number(event.properties[metric]) || 0;
    current[metric] = Number(current[metric]) + increment;
    totals.set(key, current);
  }
  return [...totals.values()].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
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
    acquisition: report("Accepted page views by page and campaign", groupedRows(
      safe, "storefront_page_viewed", ["page_key", "utm_source", "utm_campaign"], "event_count",
    )),
    product: report("Product impressions, selections and attention", [
      ...groupedRows(safe, "storefront_product_impressed", ["surface", "product_id"], "event_count")
        .map((row) => ({ event: "storefront_product_impressed", ...row })),
      ...groupedRows(safe, "storefront_product_selected", ["surface", "product_id"], "event_count")
        .map((row) => ({ event: "storefront_product_selected", ...row })),
      ...groupedRows(safe, "storefront_product_attention_summary", ["product_id"], "active_seconds")
        .map((row) => ({ event: "storefront_product_attention_summary", ...row })),
    ]),
    search: report("Search and merchandising outcomes", groupedRows(
      safe, "storefront_search_results_viewed", ["availability", "sort_order", "query_present"], "result_count",
    )),
  };
}
