import { describe, expect, it } from "vitest";

import type { SaleLinePrice, SalePricePreview } from "@/lib/api";

import { alignPreviewLines, anyLineBlocked, blockedReason, formatDiscount, mayBePriced } from "./sale-preview";

function line(sku_id: string | null, inc_vat: string): SaleLinePrice {
  return {
    sku_id, qty: 1, discount_percent: "0", unit_ex_vat: "100.00", unit_inc_vat: "115.00",
    resolved_unit_ex_vat: "100.00", before_discount_ex_vat: "100.00", ex_vat: "100.00",
    vat_amount: "15.00", inc_vat, source: sku_id ? "retail" : "manual",
    price_warning: null, suspect_price_warning: null, blocked_by: null, quantity_rule: null,
  };
}

function preview(lines: SaleLinePrice[]): SalePricePreview {
  return {
    classification: "Retail", price_list_name: null, prices_include_vat: true, vat_rate: "0.1500",
    before_discount_ex_vat: "0", before_discount_inc_vat: "0", subtotal_ex_vat: "0",
    vat_amount: "0", total_inc_vat: "0", price_revision: "r", lines,
  };
}

describe("alignPreviewLines", () => {
  it("matches preview lines to request lines by order, free-text lines included", () => {
    const aligned = alignPreviewLines(["a", "b", null], preview([line("a", "1"), line("b", "2"), line(null, "3")]));
    expect(aligned.map((entry) => entry?.inc_vat)).toEqual(["1", "2", "3"]);
  });

  it("hides lines from a stale preview instead of showing another product's amount", () => {
    const aligned = alignPreviewLines(["b", "a", "c"], preview([line("a", "1"), line("a", "1")]));
    expect(aligned).toEqual([undefined, line("a", "1"), undefined]);
  });

  it("shows nothing before the preview arrives", () => {
    expect(alignPreviewLines(["a"], undefined)).toEqual([undefined]);
  });
});

describe("blockedReason", () => {
  it("names the permission the server will ask for", () => {
    expect(blockedReason(null)).toBeNull();
    // Worded by the server on the line itself (`quantity_rule`).
    expect(blockedReason("quantity_rule")).toBeNull();
    expect(blockedReason("till.discount")).toContain("Apply discounts");
    expect(blockedReason("sales.price_override")).toContain("Override unit prices");
    expect(blockedReason("users.manage")).toContain("above the team's cap");
  });
});

describe("formatDiscount", () => {
  it("shows a stored discount and leaves legacy net units without one", () => {
    expect(formatDiscount("10.00")).toBe("10%");
    expect(formatDiscount("12.50")).toBe("12.5%");
    expect(formatDiscount("0.00")).toBe("—");
    expect(formatDiscount(null)).toBe("—");
  });
});

describe("mayBePriced", () => {
  const sku = { retail_ex_vat: "0", wholesale_ex_vat: "50.00", stockist_ex_vat: null, decorator_ex_vat: null };
  const lists = [{ id: "hand", name: "Smith & Co" }, { id: "cin7", name: "Cin7 Tier 4" }];
  const customer = (price_classification: "Retail" | "Wholesale" | "Stockist", price_list_id: string | null = null) =>
    ({ price_classification, price_list_id });

  it("offers a walk-in only what Retail prices", () => {
    expect(mayBePriced(sku, null, lists)).toBe(false);
    expect(mayBePriced({ ...sku, retail_ex_vat: "80.00" }, null, lists)).toBe(true);
  });

  it("offers the customer's own tier, or Retail as the server's fallback", () => {
    expect(mayBePriced(sku, customer("Wholesale"), lists)).toBe(true);
    expect(mayBePriced(sku, customer("Stockist"), lists)).toBe(false);
    expect(mayBePriced({ ...sku, retail_ex_vat: "80.00" }, customer("Stockist"), lists)).toBe(true);
  });

  it("leaves a hand-made price list's SKUs to the server, but not a Cin7 list's", () => {
    const none = { ...sku, wholesale_ex_vat: null };
    expect(mayBePriced(none, customer("Retail", "hand"), lists)).toBe(true);
    expect(mayBePriced(none, customer("Retail", "cin7"), lists)).toBe(false);
    expect(mayBePriced(sku, customer("Retail", "cin7"), lists)).toBe(false);
  });
});

describe("anyLineBlocked", () => {
  it("is true when the server will refuse a line", () => {
    expect(anyLineBlocked(undefined)).toBe(false);
    expect(anyLineBlocked(preview([line("a", "1")]))).toBe(false);
    expect(anyLineBlocked(preview([line("a", "1"), { ...line("b", "2"), blocked_by: "till.discount" }]))).toBe(true);
  });
});
