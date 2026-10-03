import { describe, expect, it } from "vitest";
import { sanitizeAnalyticsEvent } from "./events";
import { CONSENTED_MEASUREMENT_DISCLAIMER, consentedBrowsingReports } from "./reports";

describe("consented browsing reports", () => {
  it("labels every report as consented visitors, not a census", () => {
    const page = sanitizeAnalyticsEvent({
      name: "storefront_page_viewed",
      properties: { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale" },
    });
    const search = sanitizeAnalyticsEvent({
      name: "storefront_search_results_viewed",
      properties: { query_present: true, result_count: 1, availability: "all", sort_order: "default", price_filter_active: false },
    });
    const attention = sanitizeAnalyticsEvent({
      name: "storefront_product_attention_summary",
      properties: { product_id: "prod_test_chair", active_seconds: 10, visibility_threshold: "half_visible" },
    });
    const reports = consentedBrowsingReports([page!, search!, attention!]);

    expect(reports.acquisition.disclaimer).toBe(CONSENTED_MEASUREMENT_DISCLAIMER);
    expect(reports.product.scope).toBe("consented_visitors");
    expect(reports.search.denominators).toBe("matching_consent_scope");
    expect(reports.acquisition.rows[0]).toMatchObject({ page_key: "shop", utm_source: "spring_news" });
    expect(reports.search.rows[0]).toMatchObject({ query_present: true, result_count: 1 });
    expect(reports.product.rows.some((row) => row.product_id === "prod_test_chair" && row.active_seconds === 10)).toBe(true);
    expect(JSON.stringify(reports)).not.toContain("alice@example.com");
  });
});
