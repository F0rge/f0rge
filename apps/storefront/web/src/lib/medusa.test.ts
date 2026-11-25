import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const { listedPiece, saleOriginal, swatchHex } = await import("./medusa");
import type { MedusaVariant, StoreProduct } from "./medusa";

const price = (calculated: number, original: number | null, type: string | null, currency = "zar"): MedusaVariant["calculated_price"] => ({
  calculated_amount: calculated, original_amount: original, currency_code: currency, calculated_price: { price_list_type: type },
});
const variant = (overrides: Partial<MedusaVariant> = {}): MedusaVariant => ({
  id: "variant_simone_grey", sku: "SIMONE-GREY", title: "Grey velvet", inventory_quantity: 1, options: [], images: [],
  calculated_price: price(29_600, 29_600, null), ...overrides,
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
});
