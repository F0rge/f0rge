import { describe, expect, it } from "vitest";

import { formatArchiveCurrency, formatSettlementAmount, formatSourceAmount, sourceReportAmountText } from "./source-history";

describe("source history amounts", () => {
  it("shows every source tax and gross decimal while retaining a two-place minimum", () => {
    expect(formatArchiveCurrency("15.0015")).toBe("R 15.0015");
    expect(formatArchiveCurrency("115.0015")).toBe("R 115.0015");
    expect(formatArchiveCurrency("20.0015")).toBe("R 20.0015");
    expect(formatArchiveCurrency("100.0000")).toBe("R 100.00");
    expect(formatArchiveCurrency("15.10")).toBe("R 15.10");
    expect(formatArchiveCurrency("-115.0015")).toBe("R -115.0015");
    expect(formatArchiveCurrency("-15.10")).toBe("R -15.10");
    expect(formatArchiveCurrency("0")).toBe("R 0.00");
    expect(formatArchiveCurrency("15.0015", "USD")).toBe("USD 15.0015");
    expect(formatArchiveCurrency(null)).toBe("—");
    expect(formatArchiveCurrency("999999999999.9999")).toBe("R 999999999999.9999");
    expect(formatArchiveCurrency("-123456789012.0001")).toBe("R -123456789012.0001");
  });

  it("never shows an unknown source amount as a real zero payment or balance", () => {
    expect(formatSourceAmount("0.00", {
      source_amounts_known: false,
      source_currency_known: false,
    })).toBe("Not provided in source");
    expect(formatSourceAmount(null, {
      source_amounts_known: true,
      source_currency_known: true,
    })).toBe("Not provided in source");
  });

  it("keeps exact provided costs while explaining that their currency was absent", () => {
    expect(formatSourceAmount("12.3456", {
      source_amounts_known: true,
      source_currency_known: false,
    })).toBe("12.3456 · Currency not provided in source");
  });

  it("retains normal formatting for live known amounts, including a real zero", () => {
    expect(formatSourceAmount("0.00", {
      source_amounts_known: true,
      source_currency_known: true,
    }, (value) => `Known ${value}`)).toBe("Known 0.00");
  });

  it("preserves original report costs and totals independently with all decimal digits", () => {
    expect(sourceReportAmountText("12.3456789012345")).toBe("12.3456789012345");
    expect(sourceReportAmountText("9876.5400000000001")).toBe("9876.5400000000001");
    expect(sourceReportAmountText("0")).toBe("0");
    expect(sourceReportAmountText(null)).toBe("Not provided in source");
    expect(formatSourceAmount("0", {
      source_amounts_known: false,
      source_currency_known: false,
    })).toBe("Not provided in source");
  });

  it("distinguishes omitted archive settlements from genuine live zeros and unpaid balances", () => {
    expect(formatSettlementAmount("0.00", true)).toBe("Not imported");
    expect(formatSettlementAmount("1150.00", true)).toBe("Not imported");
    expect(formatSettlementAmount("0.00", false, (value) => `Known ${value}`)).toBe("Known 0.00");
    expect(formatSettlementAmount("1150.00", false, (value) => `Known ${value}`)).toBe("Known 1150.00");
  });
});
