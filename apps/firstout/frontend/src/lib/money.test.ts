import { describe, expect, it } from "vitest";

import { exVatToIncVat, incVatToExVat, roundHalfUp, vatPercentLabel } from "./money";

// ADR 0003: the browser converts at the rate it is given, never a built-in 15%.
describe("VAT conversions", () => {
  it("convert at the given rate", () => {
    expect(exVatToIncVat(100, "0.1600")).toBe(116);
    expect(incVatToExVat(116, "0.1600")).toBe(100);
    expect(exVatToIncVat(100, "0.1500")).toBe(115);
    expect(incVatToExVat(100, "0.1600")).toBe(86.21);
  });

  it("round float ties up, as the server's Decimal half-up does", () => {
    expect(exVatToIncVat(1739.1, "0.1500")).toBe(1999.97);
    expect(roundHalfUp(1.005)).toBe(1.01);
    expect(roundHalfUp(-1.005)).toBe(-1.01);
    // Every cent from R0.01 to R3 000 ex VAT agrees with exact integer half-up at 15%.
    for (let cents = 1; cents <= 300_000; cents += 1) {
      const exact = Math.floor((cents * 115 + 50) / 100) / 100;
      if (exVatToIncVat(cents / 100, "0.1500") !== exact) throw new Error(`differs at ${cents}`);
    }
  });

  it("label the rate as a percentage", () => {
    expect(vatPercentLabel("0.1500")).toBe("15%");
    expect(vatPercentLabel("0.1550")).toBe("15.5%");
    expect(vatPercentLabel("0.0000")).toBe("0%");
  });
});
