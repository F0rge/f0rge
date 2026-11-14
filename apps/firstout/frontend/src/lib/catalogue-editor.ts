import { ApiError, type Sku, type UpdateSkuPricePayload } from "./api";

export const CATALOGUE_PRICE_FIELDS = [
  "stockist_inc_vat",
  "wholesale_inc_vat",
  "decorator_inc_vat",
  "retail_inc_vat",
] as const;

export const CATALOGUE_FIELD_TABS = {
  name: 0,
  design: 0,
  fabric: 0,
  our_ref: 0,
  our_barcode: 0,
  category: 0,
  stockist_inc_vat: 1,
  wholesale_inc_vat: 1,
  decorator_inc_vat: 1,
  retail_inc_vat: 1,
  preferred_supplier_id: 2,
  supplier_ref: 2,
  lead_time_days: 2,
  carton_count: 2,
  reorder_min: 2,
} as const;

export type CatalogueEditorField = keyof typeof CATALOGUE_FIELD_TABS;
export type CatalogueEditorForm = Record<CatalogueEditorField, string>;
export type CatalogueEditorErrors = Partial<
  Record<CatalogueEditorField, string>
>;
type EditableSku = Pick<Sku, CatalogueEditorField>;

export function catalogueFormFromSku(sku: EditableSku): CatalogueEditorForm {
  return {
    name: sku.name,
    design: sku.design,
    fabric: sku.fabric,
    our_ref: sku.our_ref,
    our_barcode: sku.our_barcode,
    category: sku.category ?? "",
    stockist_inc_vat: sku.stockist_inc_vat ?? "",
    wholesale_inc_vat: sku.wholesale_inc_vat ?? "",
    decorator_inc_vat: sku.decorator_inc_vat ?? "",
    retail_inc_vat: sku.retail_inc_vat ?? "",
    preferred_supplier_id: sku.preferred_supplier_id ?? "",
    supplier_ref: sku.supplier_ref ?? "",
    lead_time_days:
      sku.lead_time_days === null ? "" : String(sku.lead_time_days),
    carton_count: String(sku.carton_count),
    reorder_min: sku.reorder_min === null ? "" : String(sku.reorder_min),
  };
}

export function validateCatalogueForm(
  form: CatalogueEditorForm,
): CatalogueEditorErrors {
  const errors: CatalogueEditorErrors = {};
  for (const field of [
    "name",
    "design",
    "fabric",
    "our_ref",
    "our_barcode",
  ] as const) {
    if (!form[field].trim()) errors[field] = "This field is required.";
  }
  for (const field of [
    "our_ref",
    "our_barcode",
    "category",
    "supplier_ref",
  ] as const) {
    if (form[field].trim().length > 64)
      errors[field] = "Use no more than 64 characters.";
  }
  for (const field of CATALOGUE_PRICE_FIELDS) {
    const value = form[field].trim();
    if (
      value &&
      (!/^\d+(?:\.\d{1,2})?$/.test(value) || !Number.isFinite(Number(value)))
    ) {
      errors[field] =
        "Enter a price of 0 or more with up to 2 decimal places, or leave blank.";
    }
  }
  for (const field of [
    "lead_time_days",
    "carton_count",
    "reorder_min",
  ] as const) {
    const value = form[field].trim();
    const minimum = field === "lead_time_days" ? 0 : 1;
    if (!value && field !== "carton_count") continue;
    if (
      !/^\d+$/.test(value) ||
      !Number.isSafeInteger(Number(value)) ||
      Number(value) < minimum ||
      Number(value) > 2_147_483_647
    ) {
      errors[field] =
        `Enter a whole number from ${minimum} to 2147483647${field === "carton_count" ? "." : ", or leave blank."}`;
    }
  }
  return errors;
}

/** Omit untouched fields, preserving nulls and made-to-order settings on the server. */
export function buildCatalogueUpdate(
  sku: EditableSku,
  form: CatalogueEditorForm,
): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = {};
  for (const field of [
    "name",
    "design",
    "fabric",
    "our_ref",
    "our_barcode",
  ] as const) {
    if (form[field].trim() !== sku[field].trim())
      payload[field] = form[field].trim();
  }
  for (const field of [
    "category",
    "preferred_supplier_id",
    "supplier_ref",
  ] as const) {
    const value = form[field].trim() || null;
    if (value !== (sku[field]?.trim() || null)) payload[field] = value;
  }
  for (const field of ["lead_time_days", "reorder_min"] as const) {
    const value = form[field].trim() ? Number(form[field]) : null;
    if (value !== sku[field]) payload[field] = value;
  }
  if (Number(form.carton_count) !== sku.carton_count)
    payload.carton_count = Number(form.carton_count);
  for (const field of CATALOGUE_PRICE_FIELDS) {
    const value = form[field].trim() ? Number(form[field]) : null;
    const original = sku[field] === null ? null : Number(sku[field]);
    // The API derives the matching ex-VAT value atomically, using decimal HALF_UP.
    if (value !== original)
      payload[field] = value === null ? null : form[field].trim();
  }
  return payload;
}

export function firstCatalogueError(
  errors: CatalogueEditorErrors,
): CatalogueEditorField | undefined {
  return (Object.keys(CATALOGUE_FIELD_TABS) as CatalogueEditorField[]).find(
    (field) => errors[field],
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Map existing API validation and uniqueness errors to their visible form fields. */
export function catalogueSaveFailure(error: unknown): {
  message: string;
  fields: CatalogueEditorErrors;
} {
  const fields: CatalogueEditorErrors = {};
  if (!(error instanceof ApiError)) {
    return {
      message:
        "Could not save this SKU. Check your connection and try again. Your changes are still here.",
      fields,
    };
  }
  const message = error.message;
  if (error.status === 409) {
    if (message.includes("our_ref"))
      fields.our_ref = "This reference is already used by another SKU.";
    else if (message.includes("our_barcode"))
      fields.our_barcode = "This barcode is already used by another SKU.";
    else if (message.includes("design and fabric")) {
      fields.design = "This design and fabric combination already exists.";
      fields.fabric = "Choose a different design or fabric combination.";
    }
  }
  if (error.status === 422 && Array.isArray(error.detail)) {
    for (const issue of error.detail) {
      if (!isRecord(issue) || !Array.isArray(issue.loc)) continue;
      const locations = issue.loc;
      const field = (
        Object.keys(CATALOGUE_FIELD_TABS) as CatalogueEditorField[]
      ).find((candidate) => locations.includes(candidate));
      if (field)
        fields[field] =
          typeof issue.msg === "string" ? issue.msg : "Check this value.";
    }
  }
  if (error.status === 404 && message.toLowerCase().includes("supplier")) {
    fields.preferred_supplier_id =
      "This supplier is no longer available. Choose another supplier or leave blank.";
  }
  return {
    message:
      error.status === 403
        ? "You no longer have permission to edit this SKU. Your changes have not been saved."
        : error.status >= 500
          ? "The SKU could not be saved. Your changes are still here. Try again after checking the connection."
          : message,
    fields,
  };
}
