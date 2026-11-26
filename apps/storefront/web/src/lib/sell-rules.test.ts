import { describe, expect, it } from "vitest";
import { batchPriceLine, roundDownToMultiple, sellCount, sellRules } from "./sell-rules";

// en-ZA separates thousands with a (narrow) no-break space; normalise for readable expectations.
const line = (unit: number, multiple: number, minimum: number) =>
  batchPriceLine(unit, "zar", { multiple, minimum })?.replace(/\s/g, " ") ?? null;

describe("batchPriceLine", () => {
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
    expect(batchPriceLine(10, "usd", { multiple: 2, minimum: 2 })).toBeNull();
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
