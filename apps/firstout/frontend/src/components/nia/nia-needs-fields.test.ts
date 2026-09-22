import { describe, expect, it } from "vitest";

import { coerceNeedsFieldsValues, initialFieldValues } from "./nia-structured-card";

describe("coerceNeedsFieldsValues", () => {
  it("builds a resume fields payload from the form values", () => {
    const fields = [
      { id: "our_ref", label: "Our ref", type: "text", required: true },
      { id: "carton_count", label: "Carton count", type: "number", required: false },
      { id: "hold_stock", label: "Hold stock", type: "boolean", required: false },
    ];
    const payload = coerceNeedsFieldsValues(fields, {
      our_ref: "VEL-SOF-0123",
      carton_count: "2",
      hold_stock: "true",
    });
    expect(payload).toEqual({
      our_ref: "VEL-SOF-0123",
      carton_count: 2,
      hold_stock: true,
    });
  });

  it("omits blank fields so optional values stay unset", () => {
    const fields = [{ id: "category", label: "Category", type: "text", required: false }];
    expect(coerceNeedsFieldsValues(fields, { category: "  " })).toEqual({});
  });
});

describe("initialFieldValues", () => {
  it("maps barcode onto our_barcode", () => {
    const values = initialFieldValues({
      kind: "needs_fields",
      action_id: "create_sku",
      title: "Create SKU",
      body: "Fill in the required fields to continue.",
      fields: [
        { id: "name", label: "Name", type: "text", required: true, value: "Nia Test" },
        { id: "our_barcode", label: "Our barcode", type: "text", required: true },
      ],
      values: { name: "Nia Test", barcode: "9900002026090301" },
      source: "fields",
    });
    expect(values.our_barcode).toBe("9900002026090301");
    expect(values.name).toBe("Nia Test");
  });
});
