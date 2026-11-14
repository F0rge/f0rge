import { describe, expect, it } from "vitest";
import { formatQuantity, isQuantity, MAX_QUANTITY, quantityError } from "./quantity";

describe("stock quantity boundaries", () => {
  it("preserves the smallest stock unit and the Numeric(14,4) boundary", () => {
    expect(isQuantity(0.0001)).toBe(true);
    expect(isQuantity(2.9001)).toBe(true);
    expect(isQuantity(MAX_QUANTITY)).toBe(true);
    expect(isQuantity(10_000_000_000)).toBe(false);
  });

  it("rejects excess precision instead of changing the amount", () => {
    expect(quantityError(0.00001)).toBe("Use at most 4 decimal places.");
    expect(isQuantity(1.23456)).toBe(false);
    expect(isQuantity(1e-4)).toBe(true);
    expect(isQuantity(1e-5)).toBe(false);
  });

  it("keeps empty counts distinct from zero and allows only nonnegative counts", () => {
    expect(isQuantity("", "nonnegative")).toBe(false);
    expect(isQuantity(0, "nonnegative")).toBe(true);
    expect(isQuantity(-0.0001, "nonnegative")).toBe(false);
  });

  it("allows signed nonzero stock adjustments, but positive transfers only", () => {
    expect(isQuantity(-0.1256, "delta")).toBe(true);
    expect(isQuantity(0.1256, "delta")).toBe(true);
    expect(isQuantity(0, "delta")).toBe(false);
    expect(isQuantity(-0.1256)).toBe(false);
    expect(isQuantity(0)).toBe(false);
  });

  it("rejects nonfinite values for every movement mode", () => {
    for (const value of [NaN, Infinity, -Infinity]) {
      for (const mode of ["positive", "nonnegative", "delta"] as const) {
        expect(isQuantity(value, mode)).toBe(false);
      }
    }
  });

  it("shows four decimals when present without forcing integer or trailing zero formatting", () => {
    expect(formatQuantity(2.9001)).toBe("2.9001");
    expect(formatQuantity(0.0001)).toBe("0.0001");
    expect(formatQuantity(2.9)).toBe("2.9");
    expect(formatQuantity(3)).toBe("3");
    expect(formatQuantity(0.1 + 0.2)).toBe("0.3");
  });
});
