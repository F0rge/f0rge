/**
 * Per-card editing in the SKU full view: each card's form, validation, the payload of only
 * the fields that changed, and mapping server refusals onto fields. Pure, so it is tested.
 */
import { ApiError, type Sku, type UpdateSkuPricePayload } from "./api";
import type { SkuSupplierPrice, SkuSupplierPricesReplace } from "./catalogue-lists";
import { skuDetailsFormFromSku, skuDetailsPayload, validateSkuDetails, type SkuDetailsForm } from "./sku-details";
import { buildSkuPriceChanges, skuPriceFormFromSku, validateSkuPriceForm, type SkuPriceForm } from "./sku-price-form";

export type CardErrors = Record<string, string>;
const MAX_INT = 2_147_483_647;
const MAX_SELL_QTY = 100_000;

/** "" or a whole number in range; returns the error text or null. */
function wholeNumberError(value: string, minimum: number, maximum = MAX_INT, required = false): string | null {
  const text = value.trim();
  if (!text) return required ? "Enter a value." : null;
  if (!/^\d+$/.test(text) || Number(text) < minimum || Number(text) > maximum) {
    return `Enter a whole number from ${minimum} to ${maximum}${required ? "." : ", or leave blank."}`;
  }
  return null;
}
const optionalNumber = (value: string): number | null => (value.trim() ? Number(value.trim()) : null);
const text = (value: string | null | undefined) => value ?? "";
const count = (value: number | null | undefined) => (value === null || value === undefined ? "" : String(value));

/** True when the draft differs from the form the edit started with. */
export function formChanged<T>(initial: T, draft: T): boolean {
  return JSON.stringify(initial) !== JSON.stringify(draft);
}

/* ---------- Overview ---------- */

export type OverviewForm = SkuDetailsForm & {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  category_id: string;
  subcategory_id: string;
  colour_name: string;
  main_material_id: string;
  other_material_ids: string[];
  carton_count: string;
  is_sellable: boolean;
  do_not_reorder: boolean;
  till_no_stock_required: boolean;
};

export function overviewFormFromSku(sku: Sku): OverviewForm {
  return {
    ...skuDetailsFormFromSku(sku),
    our_ref: sku.our_ref,
    our_barcode: sku.our_barcode,
    name: sku.name,
    design: sku.design,
    category_id: text(sku.category_id),
    subcategory_id: text(sku.subcategory_id),
    colour_name: text(sku.colour_name),
    main_material_id: text(sku.main_material_id),
    other_material_ids: [...sku.other_material_ids],
    carton_count: String(sku.carton_count),
    is_sellable: sku.is_sellable,
    do_not_reorder: sku.do_not_reorder,
    till_no_stock_required: sku.till_no_stock_required ?? false,
  };
}

export function validateOverview(form: OverviewForm): CardErrors {
  const errors: CardErrors = { ...validateSkuDetails(form) } as CardErrors;
  for (const field of ["our_ref", "our_barcode", "name", "design"] as const) {
    if (!form[field].trim()) errors[field] = "Enter a value.";
  }
  for (const field of ["our_ref", "our_barcode", "colour_name"] as const) {
    if (form[field].trim().length > 64) errors[field] = "Use no more than 64 characters.";
  }
  const cartons = wholeNumberError(form.carton_count, 1, MAX_INT, true);
  if (cartons) errors.carton_count = cartons;
  return errors;
}

export function overviewPayload(sku: Sku, form: OverviewForm): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = { ...skuDetailsPayload(form, sku) };
  for (const field of ["our_ref", "our_barcode", "name", "design"] as const) {
    if (form[field].trim() !== sku[field]) payload[field] = form[field].trim();
  }
  for (const field of ["category_id", "subcategory_id", "colour_name", "main_material_id"] as const) {
    const value = form[field].trim() || null;
    if (value !== (sku[field] ?? null)) payload[field] = value;
  }
  // The server keeps a sub-category only while it belongs to the category, so send both together.
  if ("category_id" in payload && !("subcategory_id" in payload)) payload.subcategory_id = form.subcategory_id || null;
  if (form.other_material_ids.join() !== sku.other_material_ids.join()) payload.other_material_ids = form.other_material_ids;
  if (Number(form.carton_count) !== sku.carton_count) payload.carton_count = Number(form.carton_count);
  for (const field of ["is_sellable", "do_not_reorder"] as const) {
    if (form[field] !== sku[field]) payload[field] = form[field];
  }
  if (form.till_no_stock_required !== (sku.till_no_stock_required ?? false)) {
    payload.till_no_stock_required = form.till_no_stock_required;
  }
  return payload;
}

/* ---------- Pricing ---------- */

export type PricingForm = SkuPriceForm & {
  sell_multiple: string;
  min_sell_qty: string;
  earns_commission: boolean;
};

export function pricingFormFromSku(sku: Sku): PricingForm {
  return {
    ...skuPriceFormFromSku(sku),
    sell_multiple: String(sku.sell_multiple),
    min_sell_qty: String(sku.min_sell_qty),
    earns_commission: !sku.exclude_from_commission,
  };
}

/** The minimum follows the multiple until the user edits the minimum in this edit. */
export function withSellMultiple(form: PricingForm, multiple: string, minimumTouched: boolean): PricingForm {
  return { ...form, sell_multiple: multiple, min_sell_qty: minimumTouched ? form.min_sell_qty : multiple };
}

export function validatePricing(form: PricingForm, vatRate?: string): CardErrors {
  const errors: CardErrors = { ...validateSkuPriceForm(form, vatRate) } as CardErrors;
  const multiple = wholeNumberError(form.sell_multiple, 1, MAX_SELL_QTY, true);
  if (multiple) errors.sell_multiple = multiple;
  const minimum = wholeNumberError(form.min_sell_qty, 1, MAX_SELL_QTY, true);
  if (minimum) errors.min_sell_qty = minimum;
  else if (!multiple && Number(form.min_sell_qty) % Number(form.sell_multiple) !== 0) {
    errors.min_sell_qty = `Must be a multiple of ${Number(form.sell_multiple)}.`;
  }
  return errors;
}

export function pricingPayload(sku: Sku, form: PricingForm): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = { ...buildSkuPriceChanges(sku, form) };
  if (Number(form.sell_multiple) !== sku.sell_multiple) payload.sell_multiple = Number(form.sell_multiple);
  // Sent whenever the multiple changes, so the server never has to guess the minimum.
  if (Number(form.min_sell_qty) !== sku.min_sell_qty || "sell_multiple" in payload) payload.min_sell_qty = Number(form.min_sell_qty);
  if (form.earns_commission === Boolean(sku.exclude_from_commission)) payload.exclude_from_commission = !form.earns_commission;
  return payload;
}

/* ---------- Supply ---------- */

export type SupplierRowForm = {
  /** Stable React key; the saved row id, or "new-n". */
  key: string;
  saved: boolean;
  supplier_id: string;
  supplier_sku: string;
  latest_price: string;
  fixed_price: string;
  min_order_qty: string;
  pack_multiple: string;
};

export type SupplyForm = {
  preferred_supplier_id: string;
  supplier_ref: string;
  lead_time_days: string;
  reorder_min: string;
  order_up_to: string;
  mto_capacity: string;
  mto_min_days: string;
  mto_max_days: string;
  mto_expires_at: string;
  rows: SupplierRowForm[];
};

/** `<input type="datetime-local">` value in the browser's zone. */
export function localDateTimeInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function supplierRowForm(row: SkuSupplierPrice): SupplierRowForm {
  return {
    key: row.id,
    saved: true,
    supplier_id: row.supplier_id,
    supplier_sku: text(row.supplier_sku),
    latest_price: text(row.latest_price),
    fixed_price: text(row.fixed_price),
    min_order_qty: count(row.min_order_qty),
    pack_multiple: count(row.pack_multiple),
  };
}

export function newSupplierRow(key: string, supplierId: string): SupplierRowForm {
  return { key, saved: false, supplier_id: supplierId, supplier_sku: "", latest_price: "", fixed_price: "", min_order_qty: "", pack_multiple: "" };
}

export function supplyFormFromSku(sku: Sku, rows: readonly SkuSupplierPrice[]): SupplyForm {
  return {
    preferred_supplier_id: text(sku.preferred_supplier_id),
    supplier_ref: text(sku.supplier_ref),
    lead_time_days: count(sku.lead_time_days),
    reorder_min: count(sku.reorder_min),
    order_up_to: count(sku.order_up_to),
    mto_capacity: count(sku.made_to_order_capacity),
    mto_min_days: count(sku.made_to_order_lead_time_min_days),
    mto_max_days: count(sku.made_to_order_lead_time_max_days),
    mto_expires_at: localDateTimeInput(sku.made_to_order_expires_at),
    rows: rows.map(supplierRowForm),
  };
}

const PRICE = /^\d+(?:\.\d{1,4})?$/;
const MTO_FIELDS = ["mto_capacity", "mto_min_days", "mto_max_days", "mto_expires_at"] as const;

export function validateSupply(form: SupplyForm, now = Date.now()): CardErrors {
  const errors: CardErrors = {};
  if (form.supplier_ref.trim().length > 64) errors.supplier_ref = "Use no more than 64 characters.";
  for (const [field, minimum] of [["lead_time_days", 0], ["reorder_min", 1], ["order_up_to", 1]] as const) {
    const error = wholeNumberError(form[field], minimum);
    if (error) errors[field] = error;
  }
  if (!errors.reorder_min && !errors.order_up_to && form.reorder_min.trim() && form.order_up_to.trim() &&
      Number(form.order_up_to) < Number(form.reorder_min)) {
    errors.order_up_to = `Must be at least the reorder minimum (${Number(form.reorder_min)}).`;
  }
  // Made to order is all four values or none.
  const filled = MTO_FIELDS.filter((field) => form[field].trim());
  if (filled.length && filled.length < MTO_FIELDS.length) {
    for (const field of MTO_FIELDS) if (!form[field].trim()) errors[field] = "Set all four made-to-order values, or clear them all.";
  } else if (filled.length) {
    const capacity = wholeNumberError(form.mto_capacity, 0, MAX_INT, true);
    if (capacity) errors.mto_capacity = capacity;
    for (const field of ["mto_min_days", "mto_max_days"] as const) {
      const error = wholeNumberError(form[field], 1, MAX_INT, true);
      if (error) errors[field] = error;
    }
    if (!errors.mto_min_days && !errors.mto_max_days && Number(form.mto_max_days) < Number(form.mto_min_days)) {
      errors.mto_max_days = "Must be at least the minimum lead time.";
    }
    const expiry = new Date(form.mto_expires_at).getTime();
    if (!Number.isFinite(expiry) || expiry <= now) errors.mto_expires_at = "Choose a time in the future.";
  }
  const seen = new Set<string>();
  form.rows.forEach((row, index) => {
    const at = (field: string) => `rows.${index}.${field}`;
    if (!row.supplier_id) errors[at("supplier_id")] = "Choose a supplier.";
    else if (seen.has(row.supplier_id)) errors[at("supplier_id")] = "This supplier already has a row.";
    seen.add(row.supplier_id);
    if (row.supplier_sku.trim().length > 64) errors[at("supplier_sku")] = "Use no more than 64 characters.";
    for (const field of ["latest_price", "fixed_price"] as const) {
      if (row[field].trim() && !PRICE.test(row[field].trim())) errors[at(field)] = "Enter 0 or more, up to 4 decimals.";
    }
    for (const field of ["min_order_qty", "pack_multiple"] as const) {
      const error = wholeNumberError(row[field], 1);
      if (error) errors[at(field)] = error;
    }
  });
  return errors;
}

export function supplyPayload(sku: Sku, form: SupplyForm): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = {};
  for (const field of ["preferred_supplier_id", "supplier_ref"] as const) {
    const value = form[field].trim() || null;
    if (value !== (sku[field] ?? null)) payload[field] = value;
  }
  for (const field of ["lead_time_days", "reorder_min", "order_up_to"] as const) {
    const value = optionalNumber(form[field]);
    if (value !== sku[field]) payload[field] = value;
  }
  const mtoChanged = form.mto_capacity !== count(sku.made_to_order_capacity) ||
    form.mto_min_days !== count(sku.made_to_order_lead_time_min_days) ||
    form.mto_max_days !== count(sku.made_to_order_lead_time_max_days) ||
    form.mto_expires_at !== localDateTimeInput(sku.made_to_order_expires_at);
  if (mtoChanged) {
    const off = MTO_FIELDS.every((field) => !form[field].trim());
    payload.made_to_order_capacity = off ? null : Number(form.mto_capacity);
    payload.made_to_order_lead_time_min_days = off ? null : Number(form.mto_min_days);
    payload.made_to_order_lead_time_max_days = off ? null : Number(form.mto_max_days);
    payload.made_to_order_expires_at = off ? null : new Date(form.mto_expires_at).toISOString();
  }
  return payload;
}

/**
 * The replace-all body for supplier price rows, or null when nothing changed. Without
 * `stock.cost.view` prices are sent as null, which keeps the stored prices.
 */
export function supplierRowsPayload(
  saved: readonly SkuSupplierPrice[],
  rows: readonly SupplierRowForm[],
  canViewCost: boolean,
): SkuSupplierPricesReplace | null {
  if (!formChanged(saved.map(supplierRowForm), rows)) return null;
  return {
    rows: rows.map((row) => ({
      supplier_id: row.supplier_id,
      supplier_sku: row.supplier_sku.trim() || null,
      latest_price: canViewCost ? row.latest_price.trim() || null : null,
      fixed_price: canViewCost ? row.fixed_price.trim() || null : null,
      min_order_qty: optionalNumber(row.min_order_qty),
      pack_multiple: optionalNumber(row.pack_multiple),
    })),
  };
}

/* ---------- Server refusals ---------- */

const DUPLICATE_FINISH = "Another SKU already has this design, colour and material.";
/** Legacy input names the server may still report, mapped to the field the card shows. */
const FIELD_ALIASES: Record<string, string> = { category: "category_id", fabric: "colour_name" };

/** Map a failed save to field messages and one plain message for the card. Unknown fields stay in the message. */
export function cardSaveFailure(error: unknown): { message: string; fields: CardErrors } {
  const fields: CardErrors = {};
  if (!(error instanceof ApiError)) {
    return { message: "Could not save. Check your connection and try again. Your changes are still here.", fields };
  }
  const { status, message } = error;
  if (status === 422 && Array.isArray(error.detail)) {
    const unplaced: string[] = [];
    for (const issue of error.detail as { loc?: unknown; msg?: unknown }[]) {
      const loc = Array.isArray(issue?.loc) ? issue.loc.slice(issue.loc[0] === "body" ? 1 : 0).map(String) : [];
      const msg = typeof issue?.msg === "string" ? issue.msg.replace(/^Value error, /, "") : "Check this value.";
      const key = loc.length ? [FIELD_ALIASES[loc[0]] ?? loc[0], ...loc.slice(1)].join(".") : "";
      if (key && !fields[key]) fields[key] = msg;
      else if (!key) unplaced.push(msg);
    }
    return { message: unplaced.join(" ") || "Some values need attention. Your changes are still here.", fields };
  }
  if (status === 409) {
    if (message.includes("our_ref")) fields.our_ref = "Another SKU already uses this reference.";
    else if (message.includes("our_barcode")) fields.our_barcode = "Another SKU already uses this barcode.";
    else if (message === DUPLICATE_FINISH || message.includes("design and fabric")) {
      fields.design = DUPLICATE_FINISH;
      fields.colour_name = "Change the design, colour or material.";
    } else if (message.includes("Kits require stock")) fields.till_no_stock_required = message;
  }
  if (status === 404 && message.toLowerCase().includes("supplier")) {
    fields.preferred_supplier_id = "This supplier is no longer available. Choose another or leave blank.";
  }
  return {
    message: status === 403
      ? message.includes("stock.cost.view")
        ? "Removing or changing a supplier price needs cost access. Your changes are still here."
        : "You no longer have permission to edit this SKU. Your changes have not been saved."
      : status >= 500
        ? "The SKU could not be saved. Your changes are still here. Try again."
        : Object.keys(fields).length ? "Check the highlighted fields. Your changes are still here." : message,
    fields,
  };
}
