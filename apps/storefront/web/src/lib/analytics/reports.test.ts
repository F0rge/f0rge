import { describe, expect, it } from "vitest";
import { CONSENTED_MEASUREMENT_DISCLAIMER, consentedBrowsingReports } from "./reports";

describe("consented browsing reports", () => {
  it("groups allowlisted events and labels consented visitors as not a census", () => {
    const reports = consentedBrowsingReports([
      { name: "storefront_page_viewed", properties: { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale" } },
      { name: "storefront_page_viewed", properties: { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale" } },
      { name: "storefront_page_viewed", properties: { page_key: "home" } },
      { name: "storefront_product_impressed", properties: { product_id: "prod_test_chair", surface: "shop" } },
      { name: "storefront_product_impressed", properties: { product_id: "prod_test_chair", surface: "shop" } },
      { name: "storefront_product_selected", properties: { product_id: "prod_test_chair", surface: "shop" } },
      { name: "storefront_product_attention_summary", properties: { product_id: "prod_test_chair", active_seconds: 10, visibility_threshold: "half_visible" } },
      { name: "storefront_product_attention_summary", properties: { product_id: "prod_test_chair", active_seconds: 4, visibility_threshold: "half_visible" } },
      { name: "storefront_search_results_viewed", properties: { query_present: true, result_count: 3, availability: "all", sort_order: "default", price_filter_active: false, search_query: "alice@example.com" } },
      { name: "storefront_search_results_viewed", properties: { query_present: true, result_count: 1, availability: "all", sort_order: "default", price_filter_active: false } },
      { name: "storefront_search_results_viewed", properties: { query_present: false, result_count: 8, availability: "in_stock", sort_order: "price_asc", price_filter_active: true } },
      { name: "arbitrary_event", properties: { email: "alice@example.com", token: "secret" } },
    ]);

    expect(reports.acquisition.disclaimer).toBe(CONSENTED_MEASUREMENT_DISCLAIMER);
    expect(reports.product.scope).toBe("consented_visitors");
    expect(reports.search.denominators).toBe("matching_consent_scope");
    expect(reports.acquisition.rows).toEqual([
      { page_key: "home", utm_source: "(none)", utm_campaign: "(none)", event_count: 1 },
      { page_key: "shop", utm_source: "spring_news", utm_campaign: "bedroom-sale", event_count: 2 },
    ]);
    expect(reports.product.rows).toEqual([
      { event: "storefront_product_impressed", surface: "shop", product_id: "prod_test_chair", event_count: 2 },
      { event: "storefront_product_selected", surface: "shop", product_id: "prod_test_chair", event_count: 1 },
      { event: "storefront_product_attention_summary", product_id: "prod_test_chair", active_seconds: 14 },
    ]);
    expect(reports.search.rows).toEqual([
      { availability: "all", sort_order: "default", query_present: true, result_count: 4 },
      { availability: "in_stock", sort_order: "price_asc", query_present: false, result_count: 8 },
    ]);
    expect(JSON.stringify(reports)).not.toContain("alice@example.com");
    expect(JSON.stringify(reports)).not.toContain("secret");
  });
});
