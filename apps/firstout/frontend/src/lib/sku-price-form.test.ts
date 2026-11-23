import { describe, expect, it } from "vitest";

import {
  buildSkuPriceChanges,
  RETAIL_SKU_PRICE_TIER,
  SKU_PRICE_TIERS,
  skuPriceFormFromSku,
  skuPricePair,
  validateSkuPriceForm,
} from "./sku-price-form";

const sku = {
  stockist_ex_vat: "2099.00",
  stockist_inc_vat: "2413.85",
  stockist_below_cost: false,
  wholesale_ex_vat: "487.34",
  wholesale_inc_vat: "560.44",
  wholesale_below_cost: true,
  decorator_ex_vat: null,
  decorator_inc_vat: null,
  decorator_below_cost: false,
  retail_inc_vat: "1149.99",
  retail_ex_vat: "999.99",
  retail_below_cost: true,
  average_unit_cost_zar: "1450.5950",
};

describe("SKU price form", () => {
  it("initializes trade prices excl. VAT and retail incl. VAT from server values", () => {
    const form = skuPriceFormFromSku(sku);
    expect(form).toEqual({
      stockist_ex_vat: "2099.00",
      wholesale_ex_vat: "487.34",
      decorator_ex_vat: "",
      retail_inc_vat: "1149.99",
    });
    expect(buildSkuPriceChanges(sku, { ...form, stockist_ex_vat: "2099" })).toEqual({});
  });

  it("distinguishes explicit zero, clearing a value and leaving a tier alone", () => {
    const form = {
      ...skuPriceFormFromSku(sku),
      stockist_ex_vat: "0",
      wholesale_ex_vat: "",
      retail_inc_vat: "999.00",
    };
    expect(validateSkuPriceForm(form, "0.1500")).toEqual({});
    expect(buildSkuPriceChanges(sku, form)).toEqual({
      stockist_ex_vat: "0",
      wholesale_ex_vat: null,
      retail_inc_vat: "999.00",
    });
  });

  it("rejects invalid prices and an amount beyond the stored limit", () => {
    const form = {
      ...skuPriceFormFromSku(sku),
      stockist_ex_vat: "-1.00",
      wholesale_ex_vat: "1e4",
      decorator_ex_vat: "1.0001",
      retail_inc_vat: "15000000000.00",
    };
    expect(validateSkuPriceForm(form, "0.1500")).toMatchObject({
      stockist_ex_vat: expect.any(String),
      wholesale_ex_vat: expect.any(String),
      decorator_ex_vat: expect.any(String),
      retail_inc_vat: expect.any(String),
    });
  });

  it("shows both tax bases and the retail cent difference before saving", () => {
    expect(skuPricePair(sku, SKU_PRICE_TIERS[0], "2099", "0.1500", false))
      .toMatchObject({ paired: "2413.85", savedRetail: null });
    expect(skuPricePair(sku, SKU_PRICE_TIERS[0], "2100", "0.1600", false))
      .toMatchObject({ paired: "2436.00", savedRetail: null });
    expect(skuPricePair(sku, RETAIL_SKU_PRICE_TIER, "999.00", "0.1500", false))
      .toMatchObject({ paired: "868.70", savedRetail: "999.01" });
  });

  it("uses the saved below-cost flag and checks edited amounts only with cost access", () => {
    const wholesale = SKU_PRICE_TIERS[1];
    expect(skuPricePair(sku, wholesale, "487.34", "0.1500", false).belowCost).toBe(false);
    expect(skuPricePair(sku, wholesale, "487.34", "0.1500", true).belowCost).toBe(true);
    expect(skuPricePair(sku, wholesale, "1000", "0.1500", false).belowCost).toBe(false);
    expect(skuPricePair(sku, wholesale, "1000", "0.1500", true).belowCost).toBe(true);
    expect(skuPricePair(sku, wholesale, "1450.60", "0.1500", true).belowCost).toBe(false);
    expect(skuPricePair(sku, wholesale, "0", "0.1500", true).belowCost).toBe(false);
    expect(skuPricePair(sku, wholesale, "", "0.1500", true).belowCost).toBe(false);
  });
});
