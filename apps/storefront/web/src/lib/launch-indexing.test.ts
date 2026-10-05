import { describe, expect, it } from "vitest";
import { canonicalUrl, catalogueIndexable, sitemapPaths, storefrontIndexable } from "./launch-indexing";

const production = {
  STOREFRONT_INDEXING_ENABLED: "true",
  RAILWAY_ENVIRONMENT_NAME: "production",
  STOREFRONT_PRIVATE_PREVIEW: "off",
  NEXT_PUBLIC_BASE_URL: "https://collector.example",
};

describe("storefront indexing", () => {
  it("stays non-indexable without an explicit production decision", () => {
    expect(storefrontIndexable({})).toBe(false);
    expect(storefrontIndexable({ ...production, RAILWAY_ENVIRONMENT_NAME: "develop" })).toBe(false);
    expect(storefrontIndexable({ ...production, NEXT_PUBLIC_BASE_URL: "http://collector.example" })).toBe(false);
    expect(storefrontIndexable({ ...production, STOREFRONT_PRIVATE_PREVIEW: "on" })).toBe(false);
    expect(storefrontIndexable({ ...production, STOREFRONT_INDEXING_ENABLED: "false" })).toBe(false);
  });

  it("allows catalogue paths only when production indexing is on", () => {
    expect(catalogueIndexable("/shop", production)).toBe(true);
    expect(catalogueIndexable("/product/chair", production)).toBe(true);
    expect(catalogueIndexable("/collections", production)).toBe(true);
    expect(catalogueIndexable("/policies/privacy", production)).toBe(true);
    expect(catalogueIndexable("/account", production)).toBe(false);
    expect(catalogueIndexable("/account/orders/1", production)).toBe(false);
    expect(catalogueIndexable("/checkout", production)).toBe(false);
    expect(catalogueIndexable("/order/confirmation", production)).toBe(false);
    expect(catalogueIndexable("/sign-in", production)).toBe(false);
    expect(catalogueIndexable("/api/health", production)).toBe(false);
    expect(catalogueIndexable("/shop", {})).toBe(false);
  });

  it("builds a sitemap of public catalogue urls and omits account and checkout", () => {
    expect(sitemapPaths({ indexable: false, products: [{ path: "/product/chair" }], collections: [{ handle: "seating" }] })).toEqual([]);
    const paths = sitemapPaths({
      indexable: true,
      products: [{ path: "/product/chair" }, { path: "/account" }],
      collections: [{ handle: "seating" }],
    });
    expect(paths).toContain("/");
    expect(paths).toContain("/shop");
    expect(paths).toContain("/collections");
    expect(paths).toContain("/product/chair");
    expect(paths).toContain("/shop?collection=seating");
    expect(paths).toContain("/policies/privacy");
    expect(paths.some((path) => path.startsWith("/account") || path.startsWith("/checkout") || path.startsWith("/order"))).toBe(false);
  });

  it("uses the configured public origin for canonical urls", () => {
    expect(canonicalUrl("https://collector.example", "/product/chair")).toBe("https://collector.example/product/chair");
    expect(canonicalUrl("https://collector.example/", "/shop?collection=seating")).toBe("https://collector.example/shop?collection=seating");
  });
});
