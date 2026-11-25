import { describe, expect, it } from "vitest";
import { cardAlert, saleOf, showSwatches } from "./card-alert";
import type { ListedPiece, ListedVariant } from "./medusa";

const variant = (overrides: Partial<ListedVariant> = {}): ListedVariant => ({
  id: "variant_a", name: "Grey PU", price: 29_990, priceLabel: "R 29 990,00", was: null, swatch: null, availability: "in-stock", images: [],
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

describe("finish dots", () => {
  it("need two or more variants, every one with a colour", () => {
    expect(showSwatches(piece([variant({ swatch: "#9b9592" }), variant({ id: "b", swatch: "#b8902e" })]))).toBe(true);
    expect(showSwatches(piece([variant({ swatch: "#9b9592" }), variant({ id: "b" })]))).toBe(false);
    expect(showSwatches(piece([variant({ swatch: "#9b9592" })]))).toBe(false);
  });
});
