import { describe, expect, it } from "vitest";
import { addableRange, batchPriceParts, coversMinimum, roundDownToMultiple, sellCount, sellRules } from "./sell-rules";

// en-ZA separates thousands with a (narrow) no-break space; normalise for readable expectations.
const line = (unit: number, multiple: number, minimum: number) =>
  batchPriceParts(unit, "zar", { multiple, minimum })?.join(" · ").replace(/\s/g, " ") ?? null;

describe("batchPriceParts", () => {
  it("names pairs, sets and minimums in the approved pattern", () => {
    expect(line(2450, 2, 2)).toBe("R 2 450,00 each · sold in pairs · R 4 900,00 per pair");
    expect(line(4250, 6, 6)).toBe("R 4 250,00 each · sold in sets of 6 · R 25 500,00 per set");
    expect(line(2450, 2, 4)).toBe("R 2 450,00 each · sold in pairs · minimum 4 · from R 9 800,00");
    expect(line(4250, 1, 4)).toBe("R 4 250,00 each · minimum 4 · from R 17 000,00");
  });

  it("adds nothing for a piece sold singly", () => {
    expect(line(4250, 1, 1)).toBeNull();
  });

  it("never relabels a foreign currency as rand", () => {
    expect(batchPriceParts(10, "usd", { multiple: 2, minimum: 2 })).toBeNull();
  });

  it("keeps each segment whole so the page can wrap only between them", () => {
    expect(batchPriceParts(2450, "zar", { multiple: 2, minimum: 4 })?.map((part) => part.replace(/\s/g, " "))).toEqual(
      ["R 2 450,00 each", "sold in pairs", "minimum 4", "from R 9 800,00"],
    );
  });
});

describe("addableRange", () => {
  const pairs = { multiple: 2, minimum: 2 };
  const pairsFromFour = { multiple: 2, minimum: 4 };

  it("matches the plain rule when the bag is already valid", () => {
    expect(addableRange(pairs, 5, 0)).toEqual({ least: 2, most: 4 });
    expect(addableRange(pairs, 5, 2)).toEqual({ least: 2, most: 2 });
    expect(addableRange({ multiple: 1, minimum: 1 }, 3, 1)).toEqual({ least: 1, most: 2 });
  });

  it("brings an off-rule bag back onto the rule", () => {
    // One chair already in the bag, sold in pairs: add 1 or 3 to reach 2 or 4.
    expect(addableRange(pairs, 5, 1)).toEqual({ least: 1, most: 3 });
  });

  it("holds the minimum when it is above the multiple", () => {
    expect(addableRange(pairsFromFour, 8, 0)).toEqual({ least: 4, most: 8 });
    expect(addableRange(pairsFromFour, 8, 2)).toEqual({ least: 2, most: 6 });
    expect(addableRange(pairsFromFour, 8, 4)).toEqual({ least: 2, most: 4 });
  });

  it("offers nothing when the stock cannot cover the least to add", () => {
    const one = addableRange(pairs, 1, 0);
    expect(one.most).toBeLessThan(one.least);
    const three = addableRange(pairsFromFour, 3, 0);
    expect(three).toEqual({ least: 4, most: 2 });
    expect(addableRange(pairs, 5, 4)).toEqual({ least: 2, most: 0 });
  });
});

describe("coversMinimum", () => {
  it("is false when stock rounded to the multiple falls short of the minimum", () => {
    expect(coversMinimum({ multiple: 2, minimum: 2 }, 1)).toBe(false);
    expect(coversMinimum({ multiple: 2, minimum: 4 }, 5)).toBe(true);
    expect(coversMinimum({ multiple: 2, minimum: 4 }, 3)).toBe(false);
    expect(coversMinimum({ multiple: 1, minimum: 1 }, 1)).toBe(true);
  });
});

describe("sellRules", () => {
  it("reads positive integers and treats anything else as 1", () => {
    expect(sellRules({ sell_multiple: 2, min_quantity: 4 })).toEqual({ multiple: 2, minimum: 4 });
    expect(sellRules(null)).toEqual({ multiple: 1, minimum: 1 });
    for (const bad of [0, -2, 1.5, "2", null, Number.NaN, 2 ** 60]) expect(sellCount(bad)).toBe(1);
  });

  it("raises a minimum that is off the multiple onto it", () => {
    expect(sellRules({ sell_multiple: 2 })).toEqual({ multiple: 2, minimum: 2 });
    expect(sellRules({ sell_multiple: 2, min_quantity: 3 })).toEqual({ multiple: 2, minimum: 4 });
  });
});

describe("roundDownToMultiple", () => {
  it("keeps whole multiples of the stock and never goes negative", () => {
    expect(roundDownToMultiple(5, 2)).toBe(4);
    expect(roundDownToMultiple(1, 2)).toBe(0);
    expect(roundDownToMultiple(-3, 2)).toBe(0);
    expect(roundDownToMultiple(7, 1)).toBe(7);
  });
});
