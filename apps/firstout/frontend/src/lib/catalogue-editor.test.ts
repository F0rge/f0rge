import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import {
  buildCatalogueUpdate,
  catalogueFormFromSku,
  catalogueSaveFailure,
  firstCatalogueError,
  validateCatalogueForm,
} from "./catalogue-editor";

const sku: Parameters<typeof catalogueFormFromSku>[0] = {
  our_ref: "SOF-001",
  our_barcode: "FO-SOF-001",
  name: "Luca Sofa",
  design: "Luca",
  fabric: "Linen",
  width_cm: null,
  depth_cm: null,
  height_cm: null,
  diameter_cm: null,
  notes: null,
  piece_count: null,
  category: null,
  preferred_supplier_id: null,
  supplier_ref: null,
  lead_time_days: null,
  carton_count: 1,
  till_no_stock_required: false,
  reorder_min: null,
  stockist_ex_vat: null,
  wholesale_ex_vat: null,
  decorator_ex_vat: null,
  retail_inc_vat: null,
};

describe("catalogue update payload", () => {
  it("saves a name change without inventing prices or replacing unset optional fields", () => {
    const form = { ...catalogueFormFromSku(sku), name: "  Luca Linen Sofa  " };
    expect(buildCatalogueUpdate(sku, form)).toEqual({
      name: "Luca Linen Sofa",
    });
    expect(buildCatalogueUpdate(sku, catalogueFormFromSku(sku))).toEqual({});
  });

  it("omits an untouched till setting and sends explicit changes in either direction", () => {
    const form = catalogueFormFromSku(sku);
    expect(form.till_no_stock_required).toBe(false);
    expect(buildCatalogueUpdate(sku, form)).toEqual({});
    const enabled = { ...form, till_no_stock_required: true };
    expect(buildCatalogueUpdate(sku, enabled)).toEqual({ till_no_stock_required: true });

    const service = { ...sku, till_no_stock_required: true };
    expect(buildCatalogueUpdate(service, catalogueFormFromSku(service))).toEqual({});
    expect(buildCatalogueUpdate(service, form)).toEqual({ till_no_stock_required: false });
  });

  it("distinguishes clearing a value from leaving it unchanged", () => {
    const existing = {
      ...sku,
      category: "Sofas",
      preferred_supplier_id: "supplier-id",
      supplier_ref: "LUCA",
      lead_time_days: 28,
      reorder_min: 2,
      retail_inc_vat: "9995.00",
    };
    const form = {
      ...catalogueFormFromSku(existing),
      category: "",
      preferred_supplier_id: "",
      supplier_ref: "",
      lead_time_days: "",
      reorder_min: "",
      retail_inc_vat: "",
    };
    expect(buildCatalogueUpdate(existing, form)).toEqual({
      category: null,
      preferred_supplier_id: null,
      supplier_ref: null,
      lead_time_days: null,
      reorder_min: null,
      retail_inc_vat: null,
    });
  });

  it("sends the edited basis for trade and retail without sending unchanged tiers", () => {
    const existing = { ...sku, stockist_ex_vat: "1999.00", retail_inc_vat: "9995.00" };
    expect(
      buildCatalogueUpdate(existing, {
        ...catalogueFormFromSku(existing),
        stockist_ex_vat: "2099",
        retail_inc_vat: "10995.50",
      }),
    ).toEqual({ stockist_ex_vat: "2099", retail_inc_vat: "10995.50" });
    expect(
      buildCatalogueUpdate(existing, {
        ...catalogueFormFromSku(existing),
        retail_inc_vat: "9995",
      }),
    ).toEqual({});
  });
});

describe("catalogue validation", () => {
  it("allows unknown optional values and a zero-day lead time, while cartons and reorder quantities start at one", () => {
    const form = { ...catalogueFormFromSku(sku), lead_time_days: "0" };
    expect(validateCatalogueForm(form)).toEqual({});
    const errors = validateCatalogueForm({
      ...form,
      carton_count: "0",
      reorder_min: "0",
    });
    expect(Object.keys(errors)).toEqual(["carton_count", "reorder_min"]);
  });

  it("rejects blank identity, invalid money and fractional or overflowing carton quantities", () => {
    const form = {
      ...catalogueFormFromSku(sku),
      our_barcode: " ",
      retail_inc_vat: "-1",
      carton_count: "1.5",
    };
    const errors = validateCatalogueForm(form);
    expect(firstCatalogueError(errors)).toBe("our_barcode");
    expect(errors.retail_inc_vat).toBeDefined();
    expect(errors.carton_count).toBeDefined();
    expect(
      validateCatalogueForm({
        ...catalogueFormFromSku(sku),
        carton_count: "2147483648",
      }).carton_count,
    ).toBeDefined();
  });
});

describe("catalogue API failure fields", () => {
  it("places uniqueness conflicts on their editable identity fields", () => {
    expect(
      catalogueSaveFailure(
        new ApiError(409, "A SKU with this our_barcode already exists"),
      ).fields,
    ).toEqual({ our_barcode: "This barcode is already used by another SKU." });
    expect(
      firstCatalogueError(
        catalogueSaveFailure(
          new ApiError(409, "A SKU with this design and fabric already exists"),
        ).fields,
      ),
    ).toBe("design");
  });

  it("maps FastAPI validation locations without assuming every issue has a known field", () => {
    const result = catalogueSaveFailure(
      new ApiError(422, "Validation failed", [
        { loc: ["body", "lead_time_days"], msg: "Must be a whole number" },
        { loc: ["body", "unknown_field"], msg: "Unknown" },
        null,
      ]),
    );
    expect(result.fields).toEqual({ lead_time_days: "Must be a whole number" });
  });
});

describe("measured SKU details", () => {
  it("saves measurements, notes and pieces independently of cartons", () => {
    const original = { ...sku, width_cm: 101.25, piece_count: 2, notes: "Old note" };
    const form = {
      ...catalogueFormFromSku(original),
      width_cm: "",
      depth_cm: "74.5",
      piece_count: "3",
      notes: "  Internal finish reference  ",
    };
    expect(validateCatalogueForm(form)).toEqual({});
    expect(buildCatalogueUpdate(original, form)).toEqual({
      width_cm: null,
      depth_cm: 74.5,
      piece_count: 3,
      notes: "Internal finish reference",
    });
  });

  it("rejects non-positive measurements and non-integer piece counts", () => {
    const form = { ...catalogueFormFromSku(sku), diameter_cm: "0", piece_count: "1.5" };
    expect(validateCatalogueForm(form)).toMatchObject({
      diameter_cm: expect.any(String),
      piece_count: expect.any(String),
    });
  });
});
