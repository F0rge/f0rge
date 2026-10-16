import { describe, expect, it } from "vitest";

import { isValidBomQty } from "./sku-bom-editor";

describe("isValidBomQty", () => {
  it("accepts positive quantities up to 4 decimal places", () => {
    expect(isValidBomQty(1)).toBe(true);
    expect(isValidBomQty(0.5)).toBe(true);
    expect(isValidBomQty(1.2345)).toBe(true);
  });

  it("rejects blank, zero, negative, and over-precise values", () => {
    expect(isValidBomQty("")).toBe(false);
    expect(isValidBomQty(0)).toBe(false);
    expect(isValidBomQty(-1)).toBe(false);
    expect(isValidBomQty(0.12345)).toBe(false);
  });
});
