import { describe, expect, it } from "vitest";
import type { ListedPiece, ListedVariant } from "./medusa";
import { readShopFilters, shopFacetCount, shopMatches, writeShopFilters } from "./shop-filters";

const variant = (id: string, price: number, availability: ListedVariant["availability"]): ListedVariant => ({
  id, name: id, price, priceLabel: `R${price}`, was: null, swatch: null, availability, images: [`/${id}.jpg`],
});

const pieces: ListedPiece[] = [{
  id: "table", title: "Dining table", href: "/product/group-table", price: 7499, priceLabel: "From R7499", justArrived: false,
  categories: [{ id: "dining", name: "Dining Room", handle: "dining-room" }],
  variants: [variant("gold", 7499, "made-to-order"), variant("silver", 7500, "in-stock")],
}];

describe("shop filters", () => {
  it("matches price and availability on the same purchasable SKU", () => {
    const availability = ["in-stock", "made-to-order"] as const;
    const under = readShopFilters(new URLSearchParams("price=under-7500&availability=in-stock"), true, [...availability]);
    expect(shopMatches(pieces, under)).toEqual([]);
    expect(shopFacetCount(pieces, under, "price", "7500-15000")).toBe(1);
    expect(shopMatches(pieces, { ...under, price: ["7500-15000"] })[0]).toMatchObject({
      href: "/product/group-table?variant=silver", price: 7500, priceLabel: "R7500",
      variant: { images: ["/silver.jpg"] }, variants: pieces[0].variants,
    });
  });

  it("ignores invalid and unavailable URL choices and retains unrelated parameters", () => {
    const raw = new URLSearchParams("categories=dining-room&categories=not-a-category&price=under-7500&availability=made-to-order&sort=constructor&utm_source=example");
    const filters = readShopFilters(raw, true, []);
    expect(filters).toEqual({ categories: ["dining-room"], price: ["under-7500"], availability: [], sort: "name" });
    expect(writeShopFilters(raw, filters)).toBe("utm_source=example&categories=dining-room&price=under-7500");
  });
});
