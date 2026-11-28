import { assert, describe, expect, it, vi } from "vitest";
import { productPageCopy, productStructuredData } from "./product-seo";
import { pickVariant, productVariantOptions } from "./product-variants";

vi.mock("server-only", () => ({}));
vi.stubEnv("NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY", "pk_test_fixture");
const { getStoreProduct, listedPiece, listShopProducts, listStoreProducts, saleOriginal, swatchHex, variantQuantityCaps } = await import("./medusa");
vi.unstubAllEnvs();
import type { MedusaVariant, StoreProduct } from "./medusa";

const price = (calculated: number, original: number | null, type: string | null, currency = "zar"): MedusaVariant["calculated_price"] => ({
  calculated_amount: calculated, original_amount: original, currency_code: currency, calculated_price: { price_list_type: type },
});
const variant = (overrides: Partial<MedusaVariant> = {}): MedusaVariant => ({
  id: "variant_simone_grey", sku: "SIMONE-GREY", title: "Grey velvet", inventory_quantity: 1, options: [], images: [],
  calculated_price: price(29_600, 29_600, null), ...overrides,
});

describe("shop catalogue snapshot", () => {
  it("shares a load, expires, retries after an error and leaves other catalogue reads fresh", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(0);
    let title = "Simone King Bed";
    let available = true;
    const fetchStore = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (new URL(String(input)).pathname === "/store/regions") {
        return Response.json({ regions: [{ id: "reg_fixture", currency_code: "zar" }] });
      }
      if (!available) return new Response(null, { status: 503 });
      const product: StoreProduct = {
        id: "prod_simone", handle: "firstout-group-51632a5c-8dfc-55d5-9d12-b1e05f4ac5ee", title, description: null, variants: [variant()],
      };
      return Response.json({ products: [product], count: 1 });
    });

    try {
      const first = listShopProducts();
      expect(listShopProducts()).toBe(first);
      expect(await first).toMatchObject([{ title: "Simone King Bed" }]);
      expect(fetchStore).toHaveBeenCalledTimes(2);

      clock.mockReturnValue(14_999);
      title = "Updated Simone King Bed";
      expect(await listShopProducts()).toMatchObject([{ title: "Simone King Bed" }]);
      expect(fetchStore).toHaveBeenCalledTimes(2);
      expect(await listStoreProducts()).toMatchObject([{ title }]);

      clock.mockReturnValue(15_000);
      available = false;
      await expect(listShopProducts()).rejects.toThrow("Medusa Store API returned 503");
      available = true;
      expect(await listShopProducts()).toMatchObject([{ title }]);
      expect(fetchStore).toHaveBeenCalledTimes(8);
    } finally {
      clock.mockRestore();
      fetchStore.mockRestore();
    }
  });
});

describe("sell rules", () => {
  it("reach the page and the bag caps only as positive integers", async () => {
    const pairs = variant({ id: "variant_pairs", inventory_quantity: 5, metadata: { sell_multiple: 2, min_quantity: 4 } });
    const odd = variant({ id: "variant_odd", metadata: { sell_multiple: "2", min_quantity: 0 } as unknown as MedusaVariant["metadata"] });
    const fetchStore = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (new URL(String(input)).pathname === "/store/regions") return Response.json({ regions: [{ id: "reg_fixture", currency_code: "zar" }] });
      return Response.json({ products: [{ id: "prod_pairs", handle: "firstout-11111111-1111-4111-8111-111111111111", title: "Pairs", description: null, variants: [pairs, odd] }], count: 1 });
    });
    try {
      const [product] = await listStoreProducts();
      expect(product.variants.map(({ metadata }) => [metadata?.sell_multiple, metadata?.min_quantity])).toEqual([[2, 4], [1, 1]]);
      expect(Object.fromEntries(await variantQuantityCaps(["prod_pairs"]))).toEqual({
        variant_pairs: { cap: 5, multiple: 2, minimum: 4 },
        variant_odd: { cap: 1, multiple: 1, minimum: 1 },
      });
    } finally {
      fetchStore.mockRestore();
    }
  });
});

describe("public material names", () => {
  it("projects reviewed labels to the product, listing and search metadata using the original option and variant IDs", async () => {
    const handle = "firstout-group-11111111-1111-4111-8111-111111111111";
    const axis = { id: "opt_upholstery", title: "Upholstery material" };
    const sand = { id: "opt_sand", value: "Solo 111" };
    const taupe = { id: "opt_taupe", value: "Solo 451" };
    const source: StoreProduct = {
      id: "prod_kidman", handle, title: "Kidman Corner Sofa", description: null,
      options: [{ ...axis, values: [sand, taupe] }],
      variants: [
        variant({ id: "variant_taupe", sku: "P20302PC3", title: taupe.value, options: [{ ...taupe, option: axis }] }),
        variant({ id: "variant_sand", sku: "P20307PC3", title: sand.value, options: [{ ...sand, option: axis }] }),
        variant({ id: "variant_same_finish", sku: "LARGER-SAND", title: sand.value, options: [{ ...sand, option: axis }] }),
        variant({ id: "variant_same_name", sku: "NEW-SAND", title: "Sand Fabric", options: [{ id: "opt_new_sand", value: "Sand Fabric", option: axis }] }),
        variant({ id: "variant_new", sku: "NEW", title: "New upholstery", options: [{ id: "opt_new", value: "New upholstery", option: axis }] }),
      ],
    };
    const fetchStore = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      new URL(String(input)).pathname === "/store/regions"
        ? Response.json({ regions: [{ id: "reg_fixture", currency_code: "zar" }] })
        : Response.json({ products: [source], count: 1 }));
    try {
      const page = await getStoreProduct(handle);
      assert.isNotNull(page);
      expect(page.options?.[0].values).toEqual([
        { id: sand.id, value: "Sand Fabric", sourceValue: sand.value }, { id: taupe.id, value: "Taupe Fabric", sourceValue: taupe.value },
      ]);
      expect(listedPiece(page).variants.map(({ id, name, options }) => ({ id, name, options }))).toEqual([
        { id: "variant_taupe", name: "Taupe Fabric", options: ["Taupe Fabric"] },
        { id: "variant_sand", name: "Sand Fabric", options: ["Sand Fabric"] },
        { id: "variant_same_finish", name: "Sand Fabric", options: ["Sand Fabric"] },
        { id: "variant_same_name", name: "Sand Fabric", options: ["Sand Fabric"] },
        { id: "variant_new", name: "New upholstery", options: ["New upholstery"] },
      ]);
      expect(productVariantOptions(page, "source")[0].availableValues).toEqual(["Solo 111", "Solo 451", "Sand Fabric", "New upholstery"]);
      expect(pickVariant(page.variants, page.variants[0], axis.id, "Sand Fabric")?.id).toBe("variant_same_name");
      expect(productPageCopy(page, page.variants[0]).title).toContain("Taupe Fabric");
      expect(productPageCopy(page).description).toContain("Sand Fabric");
      const data = productStructuredData(page, `/product/${handle}`, {
        NEXT_PUBLIC_BASE_URL: "https://www.daskasas.co.za", RAILWAY_ENVIRONMENT_NAME: "production",
        STOREFRONT_PRIVATE_PREVIEW: "off", STOREFRONT_INDEXING_ENABLED: "true",
      });
      expect(data).toContain('"material":"Taupe Fabric"');
      expect(data).not.toContain("Solo 451");
    } finally {
      fetchStore.mockRestore();
    }
  });

  it("expands the Casablanca legacy title only for the reviewed SKU and original spelling", async () => {
    const oldTitle = "Casablanca Dining Chair Grey PU & S/Steel";
    const fixture: StoreProduct = {
      id: "prod_casablanca", handle: "firstout-11111111-1111-4111-8111-111111111111", title: oldTitle,
      description: null, variants: [variant({ sku: "P61625" })],
    };
    const fetchStore = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
      new URL(String(input)).pathname === "/store/regions"
        ? Response.json({ regions: [{ id: "reg_fixture", currency_code: "zar" }] })
        : Response.json({ products: [fixture], count: 1 }));
    try {
      expect(await listStoreProducts()).toMatchObject([{ title: "Casablanca Dining Chair – Grey Faux Leather & Stainless Steel" }]);
      fixture.title = "Casablanca Dining Chair with a Silver Frame";
      expect(await listStoreProducts()).toMatchObject([{ title: fixture.title }]);
      fixture.title = oldTitle;
      fixture.variants[0].sku = "NEW";
      expect(await listStoreProducts()).toMatchObject([{ title: oldTitle }]);
    } finally {
      fetchStore.mockRestore();
    }
  });
});

describe("sale price", () => {
  it("comes only from a sale price list that lowers a ZAR price", () => {
    expect(saleOriginal(variant({ calculated_price: price(29_600, 34_990, "sale") }))).toBe(34_990);
    expect(saleOriginal(variant({ calculated_price: price(29_600, 34_990, "override") }))).toBeNull();
    expect(saleOriginal(variant({ calculated_price: price(29_600, 29_600, "sale") }))).toBeNull();
    expect(saleOriginal(variant({ calculated_price: price(29_600, 34_990, "sale", "usd") }))).toBeNull();
    expect(saleOriginal(variant({ calculated_price: undefined }))).toBeNull();
  });
});

describe("swatch colour", () => {
  it("accepts only lowercase #rrggbb", () => {
    expect(swatchHex("#9b9592")).toBe("#9b9592");
    for (const value of ["#9B9592", "#999", "red", "#9b9592;background:url(x)", null, 42]) expect(swatchHex(value)).toBeNull();
  });
});

describe("listed piece", () => {
  it("projects name, sale, swatch and the just-arrived tag", () => {
    const product: StoreProduct = {
      id: "prod_simone", handle: "firstout-group-51632a5c-8dfc-55d5-9d12-b1e05f4ac5ee", title: "Simone King Bed", description: null,
      tags: [{ value: "bedroom" }, { value: "just-arrived" }],
      variants: [
        variant({ metadata: { swatch_hex: "#9b9592" }, calculated_price: price(25_000, 29_600, "sale"), options: [{ id: "opt_val_grey", value: "Grey velvet" }] }),
        variant({ id: "variant_simone_gold", title: "Gold velvet", metadata: { swatch_hex: "#B8902E" } }),
      ],
    };
    const piece = listedPiece(product);
    expect(piece.justArrived).toBe(true);
    expect(piece.variants.map(({ name, options, was, swatch }) => ({ name, options, was, swatch }))).toEqual([
      { name: "Grey velvet", options: ["Grey velvet"], was: 29_600, swatch: "#9b9592" },
      { name: "Gold velvet", options: [], was: null, swatch: null },
    ]);
    expect(listedPiece({ ...product, tags: undefined }).justArrived).toBe(false);
  });
  it("does not list stock that cannot make up the minimum order as available", () => {
    const product: StoreProduct = {
      id: "prod_pairs", handle: "firstout-11111111-1111-4111-8111-111111111111", title: "Pairs", description: null,
      variants: [
        variant({ id: "variant_last_odd", inventory_quantity: 1, metadata: { sell_multiple: 2, min_quantity: 2 } }),
        variant({ id: "variant_pair_left", inventory_quantity: 2, metadata: { sell_multiple: 2, min_quantity: 2 } }),
      ],
    };
    expect(listedPiece(product).variants.map(({ availability }) => availability)).toEqual([null, "in-stock"]);
  });
});
