import { describe, expect, it } from "vitest";
import { sanitizeAnalyticsEvent } from "./events";

describe("storefront analytics event allowlist", () => {
  it("keeps only safe page and campaign fields", () => {
    expect(sanitizeAnalyticsEvent({
      name: "storefront_page_viewed",
      properties: {
        page_key: "shop",
        utm_source: "newsletter_2026",
        referrer_host: "www.example.com",
        current_url: "https://shop.example.com/shop?q=private",
      },
    })).toEqual({
      name: "storefront_page_viewed",
      properties: { page_key: "shop", utm_source: "newsletter_2026", referrer_host: "example.com" },
    });
  });

  it("never forwards a raw search query or other unexpected property", () => {
    expect(sanitizeAnalyticsEvent({
      name: "storefront_search_results_viewed",
      properties: {
        query_present: true,
        result_count: 3,
        search_query: "private note@example.com",
        current_url: "https://shop.example.com/shop?q=private",
      },
    })).toEqual({
      name: "storefront_search_results_viewed",
      properties: { query_present: true, result_count: 3, availability: "all", sort_order: "default", price_filter_active: false },
    });
  });

  it("drops invalid identifiers and unknown events", () => {
    expect(sanitizeAnalyticsEvent({
      name: "storefront_product_viewed",
      properties: { product_id: "person@example.com" },
    })).toBeNull();
    expect(sanitizeAnalyticsEvent({ name: "arbitrary_event", properties: { email: "person@example.com" } })).toBeNull();
    expect(sanitizeAnalyticsEvent({
      name: "storefront_page_viewed",
      properties: { page_key: "home", email: "person@example.com", token: "secret", utm_source: "bad source" },
    })).toEqual({ name: "storefront_page_viewed", properties: { page_key: "home" } });
  });
});
