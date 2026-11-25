import { describe, expect, it } from "vitest";
import { cardAlert, finishChoices, saleOf, startVariant } from "./card-alert";
import type { ListedPiece, ListedVariant } from "./medusa";

const variant = (overrides: Partial<ListedVariant> = {}): ListedVariant => ({
  id: "variant_a", name: "Grey PU", options: ["Grey PU"], price: 29_990, priceLabel: "R 29 990,00", was: null, swatch: null, availability: "in-stock", images: [],
  ...overrides,
});
const piece = (variants: ListedVariant[], justArrived = false): Pick<ListedPiece, "justArrived" | "variants"> => ({ justArrived, variants });

describe("card alert", () => {
  it("rounds the percentage and the saving down", () => {
    expect(saleOf(variant({ price: 29_990, was: 34_990 }))).toMatchObject({ percent: 14, saving: expect.stringMatching(/^R\s5\s000$/) });
    expect(saleOf(variant({ price: 7_999.5, was: 9_999 }))).toMatchObject({ percent: 19, saving: expect.stringMatching(/^R\s1\s999$/) });
  });

  it("is no sale without a higher pre-sale price or below 1% off", () => {
    expect(saleOf(variant({ was: null }))).toBeNull();
    expect(saleOf(variant({ price: 100, was: 100 }))).toBeNull();
    expect(saleOf(variant({ price: 995, was: 1_000 }))).toBeNull();
    expect(saleOf(variant({ price: null, was: 1_000 }))).toBeNull();
  });

  it("shows one alert: sale, then just arrived, then made to order", () => {
    const sale = variant({ price: 900, was: 1_000, availability: null });
    const madeToOrder = variant({ id: "variant_b", availability: "made-to-order" });
    expect(cardAlert(piece([sale, madeToOrder], true), sale)).toEqual({ kind: "sale", percent: 10, saving: expect.any(String) });
    expect(cardAlert(piece([sale, madeToOrder], true), madeToOrder)).toEqual({ kind: "just-arrived" });
    expect(cardAlert(piece([sale, madeToOrder]), madeToOrder)).toEqual({ kind: "made-to-order" });
  });

  it("calls a piece made to order only when no variant is in stock", () => {
    const madeToOrder = variant({ availability: "made-to-order" });
    expect(cardAlert(piece([madeToOrder, variant({ id: "variant_b" })]), madeToOrder)).toBeNull();
    expect(cardAlert(piece([variant({ availability: null })]), undefined)).toBeNull();
  });
});

describe("start variant", () => {
  const plain = variant({ id: "plain", price: 1_000 });
  it("opens on the requested variant, else the lowest-priced one", () => {
    const cheaperSale = variant({ id: "sale", price: 900, was: 1_200 });
    expect(startVariant(piece([plain, cheaperSale]))?.id).toBe("sale");
    expect(startVariant(piece([plain, cheaperSale]), "plain")?.id).toBe("plain");
    expect(startVariant(piece([plain, cheaperSale]), "variant_gone")?.id).toBe("sale");
  });

  it("shows the sale only when the on-sale variant is the one the card opens on", () => {
    const secondOnSale = piece([plain, variant({ id: "sale", price: 900, was: 1_200 })]);
    expect(cardAlert(secondOnSale, startVariant(secondOnSale))).toMatchObject({ kind: "sale", percent: 25 });
    // The sale price is above the cheapest variant, so the card opens on "From R 800" without a sale.
    const saleNotCheapest = piece([variant({ id: "cheap", price: 800 }), variant({ id: "sale", price: 900, was: 1_200 })]);
    expect(startVariant(saleNotCheapest)?.id).toBe("cheap");
    expect(cardAlert(saleNotCheapest, startVariant(saleNotCheapest))).toBeNull();
  });
});

describe("finish dots", () => {
  const umbra = [
    variant({ id: "silver_200", name: "Silver / 200 cm", options: ["Silver", "200 cm"], swatch: "#c0c0c0", price: 34_773.92 }),
    variant({ id: "gold_200", name: "Gold / 200 cm", options: ["Gold", "200 cm"], swatch: "#b8902e", price: 36_500, availability: null }),
    variant({ id: "gold_160", name: "Gold / 160 cm", options: ["Gold", "160 cm"], swatch: "#b8902e", price: 37_000 }),
  ];

  it("shows one dot per colour, opening its available variant before a cheaper unavailable one", () => {
    expect(finishChoices(piece(umbra)).map(({ swatch, name, variant: { id } }) => ({ swatch, name, id }))).toEqual([
      { swatch: "#c0c0c0", name: "Silver / 200 cm", id: "silver_200" },
      { swatch: "#b8902e", name: "Gold", id: "gold_160" },
    ]);
  });

  it("prefers the cheapest among equally available variants", () => {
    const both = [umbra[0], { ...umbra[1], availability: "in-stock" as const }, umbra[2]];
    expect(finishChoices(piece(both))[1].variant.id).toBe("gold_200");
  });

  it("needs two colours and a colour on every variant", () => {
    expect(finishChoices(piece(umbra.slice(1)))).toEqual([]);
    expect(finishChoices(piece([...umbra, variant({ id: "bronze" })]))).toEqual([]);
    expect(finishChoices(piece([umbra[0]]))).toEqual([]);
  });
});
