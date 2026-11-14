import { describe, expect, it } from "vitest";

import { formatSettlementAmount, formatSourceAmount, sourceReportAmountText } from "./source-history";

describe("source history amounts", () => {
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
