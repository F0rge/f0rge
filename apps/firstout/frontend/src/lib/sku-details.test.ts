import { describe, expect, it } from "vitest";

import { skuDetailsFormFromSku, skuDetailsPayload, validateSkuDetails } from "./sku-details";

describe("SKU swatch colour", () => {
  it("saves a lowercase #rrggbb and clears to null", () => {
    const form = skuDetailsFormFromSku({ swatch_hex: "#9b9592" });
    expect(form.swatch_hex).toBe("#9b9592");
    expect(skuDetailsPayload(form, { swatch_hex: "#9b9592" })).toEqual({});
    expect(skuDetailsPayload({ ...form, swatch_hex: " #B8902E " }, { swatch_hex: "#9b9592" })).toEqual({ swatch_hex: "#b8902e" });
    expect(skuDetailsPayload({ ...form, swatch_hex: "" }, { swatch_hex: "#9b9592" })).toEqual({ swatch_hex: null });
    expect(skuDetailsPayload(skuDetailsFormFromSku({}))).toEqual({});
  });

  it("rejects anything but # and six hex digits", () => {
    const form = skuDetailsFormFromSku({});
    for (const value of ["#999", "9b9592", "grey", "#9b95921"]) {
      expect(validateSkuDetails({ ...form, swatch_hex: value }).swatch_hex).toMatch(/six hex digits/);
    }
    expect(validateSkuDetails({ ...form, swatch_hex: "#9B9592" }).swatch_hex).toBeUndefined();
    expect(validateSkuDetails(form).swatch_hex).toBeUndefined();
  });
});
