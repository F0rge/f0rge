import { describe, expect, it } from "vitest";

import { isCin7GeneratedPriceList } from "./price-lists";

describe("isCin7GeneratedPriceList", () => {
  it("recognises the imported Cin7 lists only", () => {
    expect(isCin7GeneratedPriceList("Cin7 Retail")).toBe(true);
    expect(isCin7GeneratedPriceList("Cin7 Tier 10")).toBe(true);
    expect(isCin7GeneratedPriceList("Decorator")).toBe(false);
  });
});
