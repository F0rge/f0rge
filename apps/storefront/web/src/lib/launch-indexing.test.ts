import { beforeEach, describe, expect, it, vi } from "vitest";
import { currentCustomerPolicies, type CustomerPolicyDocument } from "./customer-policies";
import { canonicalUrl, catalogueIndexable, robotsHeader, sitemapPaths, storefrontIndexable } from "./launch-indexing";

vi.mock("./customer-policies", async (original) => ({
  ...await original<typeof import("./customer-policies")>(),
  currentCustomerPolicies: vi.fn(),
}));

const ownerFacts = vi.mocked(currentCustomerPolicies);

const production = {
  STOREFRONT_INDEXING_ENABLED: "true",
  RAILWAY_ENVIRONMENT_NAME: "production",
  STOREFRONT_PRIVATE_PREVIEW: "off",
  NEXT_PUBLIC_BASE_URL: "https://daskasas.example",
};

describe("storefront indexing", () => {
  beforeEach(() => {
    ownerFacts.mockReturnValue({} as CustomerPolicyDocument);
  });

  it("keeps the whole site noindex while the owner policy document is missing", () => {
    ownerFacts.mockReturnValue(null);
    expect(storefrontIndexable(production)).toBe(false);
    expect(catalogueIndexable("/", production)).toBe(false);
    expect(catalogueIndexable("/product/chair", production)).toBe(false);
    expect(robotsHeader("/shop", production)).toBe("noindex, nofollow, noarchive");
  });

  it("stays non-indexable without an explicit production decision", () => {
    expect(storefrontIndexable({})).toBe(false);
    expect(storefrontIndexable({ ...production, RAILWAY_ENVIRONMENT_NAME: "develop" })).toBe(false);
    expect(storefrontIndexable({ ...production, NEXT_PUBLIC_BASE_URL: "http://daskasas.example" })).toBe(false);
    expect(storefrontIndexable({ ...production, STOREFRONT_PRIVATE_PREVIEW: "on" })).toBe(false);
    expect(storefrontIndexable({ ...production, STOREFRONT_INDEXING_ENABLED: "false" })).toBe(false);
    expect(storefrontIndexable(production)).toBe(true);
  });

  it("allows catalogue paths only when production indexing is on", () => {
    expect(catalogueIndexable("/shop", production)).toBe(true);
    expect(catalogueIndexable("/product/chair", production)).toBe(true);
    expect(catalogueIndexable("/shop/bedroom", production)).toBe(true);
    expect(catalogueIndexable("/shop/not-a-category", production)).toBe(false);
    expect(catalogueIndexable("/collections", production)).toBe(false);
    expect(catalogueIndexable("/support", production)).toBe(false);
    expect(catalogueIndexable("/policies/privacy", production)).toBe(true);
    expect(catalogueIndexable("/policies/terms", production)).toBe(true);
    expect(catalogueIndexable("/policies/refunds", production)).toBe(true);
    expect(catalogueIndexable("/policies/returns", production)).toBe(true);
    expect(catalogueIndexable("/help", production)).toBe(true);
    expect(catalogueIndexable("/contact", production)).toBe(false);
    expect(catalogueIndexable("/account", production)).toBe(false);
    expect(catalogueIndexable("/account/orders/1", production)).toBe(false);
    expect(catalogueIndexable("/checkout", production)).toBe(false);
    expect(catalogueIndexable("/order/confirmation", production)).toBe(false);
    expect(catalogueIndexable("/sign-in", production)).toBe(false);
    expect(catalogueIndexable("/api/health", production)).toBe(false);
    expect(catalogueIndexable("/shop", {})).toBe(false);
  });

  it("builds a sitemap of public catalogue urls and omits account and checkout", () => {
    expect(sitemapPaths({ indexable: false, products: [{ path: "/product/chair" }] })).toEqual([]);
    const paths = sitemapPaths({
      indexable: true,
      products: [{ path: "/product/chair" }, { path: "/account" }],
    });
    expect(paths).toContain("/");
    expect(paths).toContain("/shop");
    expect(paths).not.toContain("/collections");
    expect(paths).not.toContain("/support");
    expect(paths).toContain("/product/chair");
    expect(paths).toEqual(expect.arrayContaining(["/shop/sofas-armchairs", "/shop/dining-room", "/shop/bedroom", "/shop/coffee-console-tables"]));
    expect(paths.some((path) => path.includes("?"))).toBe(false);
    expect(paths).toContain("/policies/privacy");
    expect(paths).toContain("/policies/terms");
    expect(paths).toContain("/policies/refunds");
    expect(paths).toContain("/policies/returns");
    expect(paths).toContain("/policies/delivery");
    expect(paths).toContain("/policies/paia");
    expect(paths).toContain("/help");
    expect(paths).not.toContain("/contact");
    expect(paths.some((path) => path.startsWith("/account") || path.startsWith("/checkout") || path.startsWith("/order"))).toBe(false);
  });

  it("uses the configured public origin for canonical urls", () => {
    expect(canonicalUrl("https://daskasas.example", "/product/chair")).toBe("https://daskasas.example/product/chair");
    expect(canonicalUrl("https://daskasas.example/", "/shop/bedroom")).toBe("https://daskasas.example/shop/bedroom");
  });
});
