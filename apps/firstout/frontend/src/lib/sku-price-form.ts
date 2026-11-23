import type { Sku } from "./api";
import { exVatToIncVat, formatPriceAmount, incVatToExVat, roundHalfUp } from "./money";

export const SKU_PRICE_FIELDS = [
  "stockist_ex_vat",
  "wholesale_ex_vat",
  "decorator_ex_vat",
  "retail_inc_vat",
] as const;

export type SkuPriceField = (typeof SKU_PRICE_FIELDS)[number];
export type SkuPriceForm = Record<SkuPriceField, string>;
export type SkuPriceChanges = Partial<Record<SkuPriceField, string | null>>;
export type SkuPriceErrors = Partial<Record<SkuPriceField, string>>;

export const RETAIL_SKU_PRICE_TIER = {
  field: "retail_inc_vat", paired: "retail_ex_vat", label: "Retail", belowCost: "retail_below_cost",
} as const;

export const SKU_PRICE_TIERS = [
  { field: "stockist_ex_vat", paired: "stockist_inc_vat", label: "Stockist", belowCost: "stockist_below_cost" },
  { field: "wholesale_ex_vat", paired: "wholesale_inc_vat", label: "Wholesale", belowCost: "wholesale_below_cost" },
  { field: "decorator_ex_vat", paired: "decorator_inc_vat", label: "Decorator", belowCost: "decorator_below_cost" },
  RETAIL_SKU_PRICE_TIER,
] as const;

type SkuPriceTier = (typeof SKU_PRICE_TIERS)[number];
const PRICE_INPUT = /^\d+(?:\.\d{1,2})?$/;
// The stored ex-VAT amount is Numeric(12, 2).
const MAX_EX_VAT_PRICE = 9_999_999_999.99;

export function skuPriceFormFromSku(sku: Pick<Sku, SkuPriceField>): SkuPriceForm {
  return {
    stockist_ex_vat: sku.stockist_ex_vat ?? "",
    wholesale_ex_vat: sku.wholesale_ex_vat ?? "",
    decorator_ex_vat: sku.decorator_ex_vat ?? "",
    retail_inc_vat: sku.retail_inc_vat ?? "",
  };
}

export function validateSkuPriceForm(form: SkuPriceForm, vatRate?: string): SkuPriceErrors {
  const errors: SkuPriceErrors = {};
  for (const field of SKU_PRICE_FIELDS) {
    const value = form[field].trim();
    if (!value) continue;
    const amount = Number(value);
    if (!PRICE_INPUT.test(value) || !Number.isFinite(amount)) {
      errors[field] = "Enter a price of 0 or more with up to 2 decimal places, or leave blank.";
      continue;
    }
    const ex = field === "retail_inc_vat"
      ? vatRate === undefined ? undefined : incVatToExVat(amount, vatRate)
      : amount;
    if (ex !== undefined && (!Number.isFinite(ex) || ex > MAX_EX_VAT_PRICE)) {
      errors[field] = "The price excl. VAT must be R 9,999,999,999.99 or less.";
    }
  }
  return errors;
}

function priceChanged(saved: string | null | undefined, value: string): boolean {
  const original = saved ?? "";
  const entered = value.trim();
  if (original === entered) return false;
  return !original || !PRICE_INPUT.test(entered) || Number(entered) !== Number(original);
}

/** Supply just the edited basis for each tier; the API owns persisted conversions. */
export function buildSkuPriceChanges(sku: Pick<Sku, SkuPriceField>, form: SkuPriceForm): SkuPriceChanges {
  const changes: SkuPriceChanges = {};
  for (const field of SKU_PRICE_FIELDS) {
    if (priceChanged(sku[field], form[field])) {
      changes[field] = form[field].trim() || null;
    }
  }
  return changes;
}

/** Format the counterpart for display. Invoice totals and stored prices come from the server. */
export function skuPricePair(
  sku: Pick<Sku, SkuPriceField | SkuPriceTier["paired"] | SkuPriceTier["belowCost"] | "average_unit_cost_zar">,
  tier: SkuPriceTier,
  value: string,
  vatRate: string | undefined,
  canViewCost: boolean,
): { paired: string | null; savedRetail: string | null; belowCost: boolean } {
  if (!priceChanged(sku[tier.field], value)) {
    return {
      paired: sku[tier.paired] ?? null,
      savedRetail: null,
      belowCost: canViewCost && Boolean(sku[tier.belowCost]),
    };
  }
  const entered = value.trim();
  const amount = Number(entered);
  if (!vatRate || !PRICE_INPUT.test(entered) || !Number.isFinite(amount) || amount > 2 * MAX_EX_VAT_PRICE) {
    return { paired: null, savedRetail: null, belowCost: false };
  }
  const retail = tier.field === "retail_inc_vat";
  const ex = retail ? incVatToExVat(amount, vatRate) : amount;
  const inc = exVatToIncVat(ex, vatRate);
  const cost = canViewCost && sku.average_unit_cost_zar != null
    ? roundHalfUp(Number(sku.average_unit_cost_zar))
    : null;
  return {
    paired: formatPriceAmount(retail ? ex : inc),
    savedRetail: retail && inc !== amount ? formatPriceAmount(inc) : null,
    belowCost: cost !== null && ex > 0 && ex < cost,
  };
}
