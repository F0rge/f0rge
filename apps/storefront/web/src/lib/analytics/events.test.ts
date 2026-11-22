import { describe, expect, it } from "vitest";
import { analyticsPageForPathname, analyticsSurfaceForPathname, sanitizeAnalyticsEvent } from "./events";

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

  it("allows public catalogue titles on product views and adds to bag", () => {
    const label = { product_id: "prod_chair", product_title: "Évora — 椅子 🪑" };
    const bagItem = { ...label, variant_id: "variant_chair", quantity: 1, value_minor: 249900 };

    expect(sanitizeAnalyticsEvent({
      name: "storefront_product_viewed",
      properties: { ...label, product_title: "  Évora — 椅子 🪑  ", email: "shopper@example.com" },
    })?.properties).toEqual(label);
    expect(sanitizeAnalyticsEvent({
      name: "storefront_cart_item_added",
      properties: bagItem,
    })?.properties).toMatchObject(bagItem);
    expect(sanitizeAnalyticsEvent({
      name: "storefront_cart_item_removed",
      properties: bagItem,
    })?.properties).not.toHaveProperty("product_title");
  });

  it.each([undefined, 7, " ", "x".repeat(256), "Invalid\tlabel", "Invalid\u202elabel"])(
    "keeps the product ID when a catalogue title is missing or invalid",
    (productTitle) => {
      const label = { product_id: "prod_chair", product_title: productTitle };
      const bagItem = { ...label, variant_id: "variant_chair", quantity: 1, value_minor: 249900 };

      expect(sanitizeAnalyticsEvent({
        name: "storefront_product_viewed",
        properties: label,
      })?.properties).toEqual({ product_id: "prod_chair" });
      const added = sanitizeAnalyticsEvent({
        name: "storefront_cart_item_added",
        properties: bagItem,
      });
      expect(added?.properties.product_id).toBe("prod_chair");
      expect(added?.properties).not.toHaveProperty("product_title");
    },
  );

  it("tracks the four category listings and keeps the made-to-order filter", () => {
    expect(analyticsPageForPathname("/shop/bedroom")).toEqual({ pageKey: "category" });
    expect(analyticsSurfaceForPathname("/shop/sofas-armchairs")).toBe("category");
    expect(analyticsPageForPathname("/shop/not-a-category")).toBeNull();
    expect(analyticsPageForPathname("/help")).toEqual({ pageKey: "help" });
    expect(sanitizeAnalyticsEvent({ name: "storefront_product_impressed", properties: { product_id: "prod_1", surface: "category" } }))
      .toEqual({ name: "storefront_product_impressed", properties: { product_id: "prod_1", surface: "category" } });
    expect(sanitizeAnalyticsEvent({ name: "storefront_search_results_viewed", properties: { query_present: false, result_count: 1, availability: "made_to_order" } })?.properties.availability)
      .toBe("made_to_order");
  });
});
