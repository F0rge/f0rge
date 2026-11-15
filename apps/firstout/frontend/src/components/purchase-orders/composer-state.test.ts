import { describe, expect, it } from "vitest";
import {
  createOrderPayload,
  factoryTotal,
  formatFactoryAmount,
  lineFieldId,
  newOrderDraft,
  orderRequiresApproval,
  validateOrderDraft,
  type ComposerChoices,
  type OrderDraft,
} from "./composer-state";

const choices: ComposerChoices = {
  suppliers: [
    { id: "supplier", is_archived: false, default_currency: "EUR" },
    { id: "archived", is_archived: true, default_currency: "ZAR" },
  ],
  proformas: [
    { id: "proforma", supplier_id: "supplier", is_archived: false },
    { id: "another", supplier_id: "different", is_archived: false },
    { id: "old-proforma", supplier_id: "supplier", is_archived: true },
  ],
  skus: [
    { id: "sku", is_archived: false },
    { id: "old-sku", is_archived: true },
  ],
};
function validDraft(): OrderDraft {
  const draft = newOrderDraft();
  draft.supplier_id = "supplier";
  draft.lines[0] = {
    ...draft.lines[0],
    sku_id: "sku",
    qty: 2,
    factory_unit_amount: "123.4500",
  };
  return draft;
}
describe("purchase order creation rules", () => {
  it("accepts a complete SKU line and preserves decimal costs and notes in the API payload", () => {
    const draft = validDraft();
    draft.proforma_id = "proforma";
    draft.supplier_ref = "  FACTORY-2  ";
    draft.notes = "  Inspect finish  ";
    draft.lines[0].notes = "  Olive fabric  ";
    expect(validateOrderDraft(draft, choices)).toEqual({});
    expect(createOrderPayload(draft)).toMatchObject({
      supplier_id: "supplier",
      proforma_id: "proforma",
      supplier_ref: "FACTORY-2",
      notes: "Inspect finish",
      submit_for_approval: false,
      lines: [
        {
          sku_id: "sku",
          qty: 2,
          factory_unit_amount: "123.4500",
          notes: "Olive fabric",
        },
      ],
    });
  });
  it("allows a description-only line but requires approval even when the manual option is off", () => {
    const draft = validDraft();
    draft.lines[0].sku_id = "";
    draft.lines[0].description = "Custom ottoman";
    expect(validateOrderDraft(draft, choices)).toEqual({});
    expect(orderRequiresApproval(draft)).toBe(true);
    expect(createOrderPayload(draft).lines[0].sku_id).toBeNull();
    draft.lines[0].description = "  ";
    expect(
      validateOrderDraft(draft, choices)[
        lineFieldId(draft.lines[0], "description")
      ],
    ).toContain("description");
  });
  it("keeps manual approval for an otherwise complete order", () => {
    const draft = validDraft();
    expect(orderRequiresApproval(draft)).toBe(false);
    draft.submit_for_approval = true;
    expect(orderRequiresApproval(draft)).toBe(true);
    expect(createOrderPayload(draft).submit_for_approval).toBe(true);
  });
  it("rejects missing or archived suppliers, cross-supplier proformas, and archived products", () => {
    const draft = validDraft();
    draft.supplier_id = "archived";
    expect(validateOrderDraft(draft, choices)["po-supplier"]).toBeDefined();
    draft.supplier_id = "supplier";
    for (const id of ["another", "old-proforma", "missing"]) {
      draft.proforma_id = id;
      expect(validateOrderDraft(draft, choices)["po-proforma"]).toBeDefined();
    }
    draft.proforma_id = "";
    draft.lines[0].sku_id = "old-sku";
    expect(
      validateOrderDraft(draft, choices)[lineFieldId(draft.lines[0], "sku")],
    ).toBeDefined();
  });
  it("rejects duplicate SKUs but permits multiple separately described items", () => {
    const draft = validDraft();
    draft.lines.push({ ...draft.lines[0], key: "second" });
    expect(
      validateOrderDraft(draft, choices)[lineFieldId(draft.lines[1], "sku")],
    ).toContain("already");
    draft.lines = draft.lines.map((line, index) => ({
      ...line,
      sku_id: "",
      description: `Custom item ${index + 1}`,
    }));
    expect(validateOrderDraft(draft, choices)).toEqual({});
  });
  it("rejects zero, negative, fractional and unsafe quantities", () => {
    const draft = validDraft();
    for (const qty of [
      0,
      -1,
      1.5,
      10_000_000_000,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.MAX_SAFE_INTEGER + 1,
    ]) {
      draft.lines[0].qty = qty;
      expect(
        validateOrderDraft(draft, choices)[lineFieldId(draft.lines[0], "qty")],
      ).toBeDefined();
      expect(() => createOrderPayload(draft)).toThrow();
    }
  });
  it("rejects blank, zero, negative, NaN and infinite factory amounts", () => {
    const draft = validDraft();
    for (const value of ["", "  ", "0", "0.0000", "-1", "NaN", "Infinity"]) {
      draft.lines[0].factory_unit_amount = value;
      expect(
        validateOrderDraft(draft, choices)[
          lineFieldId(draft.lines[0], "factory")
        ],
      ).toBeDefined();
      expect(() => createOrderPayload(draft)).toThrow();
    }
  });
  it("enforces schema text limits and refuses incomplete supplier-code lookup", () => {
    const draft = validDraft();
    draft.supplier_ref = "x".repeat(129);
    draft.lines[0].supplier_code = "x".repeat(129);
    draft.lines[0].description = "x".repeat(513);
    const errors = validateOrderDraft(draft, choices);
    expect(errors["po-supplier-ref"]).toBeDefined();
    expect(errors[lineFieldId(draft.lines[0], "code")]).toBeDefined();
    expect(errors[lineFieldId(draft.lines[0], "description")]).toBeDefined();
    draft.supplier_ref = "x".repeat(128);
    draft.lines[0].supplier_code = "x".repeat(128);
    draft.lines[0].description = "x".repeat(512);
    expect(validateOrderDraft(draft, choices)).toEqual({});
    draft.lines[0].supplierCodeLookup = {
      supplierId: "supplier",
      skuId: "sku",
      status: "loading",
    };
    expect(
      validateOrderDraft(draft, choices)[lineFieldId(draft.lines[0], "code")],
    ).toContain("Wait");
  });
  it("keeps reviewed costs within the database's 14 whole digits and 4 decimal places", () => {
    const draft = validDraft();
    for (const value of ["0.00001", "1.23456", "100000000000000"]) {
      draft.lines[0].factory_unit_amount = value;
      expect(
        validateOrderDraft(draft, choices)[
          lineFieldId(draft.lines[0], "factory")
        ],
      ).toBeDefined();
      expect(() => createOrderPayload(draft)).toThrow();
    }
    draft.lines[0].factory_unit_amount = "99999999999999.9999";
    expect(validateOrderDraft(draft, choices)).toEqual({});
    expect(createOrderPayload(draft).lines[0].factory_unit_amount).toBe(
      "99999999999999.9999",
    );
  });
  it("validates supplier details before requiring order-line fields", () => {
    const draft = newOrderDraft();
    draft.supplier_id = "supplier";
    expect(validateOrderDraft(draft, choices, false)).toEqual({});
    expect(
      Object.keys(validateOrderDraft(draft, choices)).length,
    ).toBeGreaterThan(0);
  });
});
describe("factory totals", () => {
  it("adds supplier amounts exactly without floating point or retail VAT", () => {
    expect(
      factoryTotal([
        { qty: 3, factory_unit_amount: "0.10" },
        { qty: 1, factory_unit_amount: "0.20" },
      ]),
    ).toBe("0.50");
    expect(
      factoryTotal([{ qty: 2, factory_unit_amount: "9007199254740.9999" }]),
    ).toBe("18014398509481.9998");
    expect(formatFactoryAmount("246.9000", "EUR")).toBe("EUR 246.90");
    expect(formatFactoryAmount("18014398509481.9998", "ZAR")).toContain(
      ".9998",
    );
  });
  it("never presents missing costs or unknown currency as known money", () => {
    expect(factoryTotal([{ qty: 1, factory_unit_amount: null }])).toBeNull();
    expect(factoryTotal([{ qty: "", factory_unit_amount: "10" }])).toBeNull();
    expect(formatFactoryAmount("100", null)).toBe("Currency unavailable");
    expect(formatFactoryAmount(null, "ZAR")).toBe("—");
  });
});
