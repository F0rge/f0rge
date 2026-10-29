import { describe, expect, it } from "vitest";

import {
  displayFabric,
  manufacturerCode,
  supplierCodeAfterSkuPick,
  supplierCodeWhenBlank,
} from "./po-supplier-code";

describe("PO supplier code prefill", () => {
  it("prefers the per-supplier factory code over the SKU supplier ref", () => {
    expect(manufacturerCode("DC-23-11G", "GENERIC-REF")).toBe("DC-23-11G");
  });

  it("falls back to the SKU supplier ref when that supplier has no code", () => {
    expect(manufacturerCode(null, "DC-23-11G")).toBe("DC-23-11G");
    expect(manufacturerCode("   ", "TOP-OAK")).toBe("TOP-OAK");
    expect(manufacturerCode(null, null)).toBe("");
  });

  it("keeps a code the user typed on the new PO form", () => {
    expect(
      supplierCodeAfterSkuPick({
        current: "TYPED-CODE",
        touched: true,
        manufacturerCode: "DC-23-11G",
      }),
    ).toBe("TYPED-CODE");
  });

  it("keeps a cleared field when the user edited it", () => {
    expect(
      supplierCodeAfterSkuPick({
        current: "",
        touched: true,
        manufacturerCode: "DC-23-11G",
      }),
    ).toBe("");
  });

  it("fills an untouched field, including when the SKU changes", () => {
    expect(
      supplierCodeAfterSkuPick({
        current: "",
        touched: false,
        manufacturerCode: "DC-23-11G",
      }),
    ).toBe("DC-23-11G");
    expect(
      supplierCodeAfterSkuPick({
        current: "OLD-AUTO",
        touched: false,
        manufacturerCode: "DC-99",
      }),
    ).toBe("DC-99");
  });

  it("does not replace a code already on a pending PO line", () => {
    expect(supplierCodeWhenBlank("HAND-ENTERED", "DC-23-11G")).toBe("HAND-ENTERED");
    expect(supplierCodeWhenBlank("   ", "DC-23-11G")).toBe("DC-23-11G");
    expect(supplierCodeWhenBlank("", "TOP-OAK")).toBe("TOP-OAK");
  });
});

describe("PO fabric column", () => {
  it("shows the SKU fabric or finish", () => {
    expect(displayFabric("Belgian linen")).toBe("Belgian linen");
    expect(displayFabric("  Oak veneer  ")).toBe("Oak veneer");
  });

  it("hides the placeholder dash and blank fabric", () => {
    expect(displayFabric("-")).toBeNull();
    expect(displayFabric(" - ")).toBeNull();
    expect(displayFabric("")).toBeNull();
    expect(displayFabric(null)).toBeNull();
    expect(displayFabric(undefined)).toBeNull();
  });
});
