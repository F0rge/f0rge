import {
  exVatToIncVat,
  formatPriceAmount,
  parsePriceInput,
  roundHalfUp,
  type CustomerCrm,
  type PriceClassification,
  type PriceList,
  type Sku,
} from "@/lib/api";

/** How a line's starting unit price was chosen. Amounts on the object are ex VAT. */
export type QuotePriceSource =
  | "price_list"
  | "stockist"
  | "wholesale"
  | "decorator"
  | "retail"
  | "retail_fallback"
  | "missing";

/** Matches `UserRole.OWNER`. Other roles see the computed price and cannot change it. */
export function canOverrideQuoteUnitPrice(role: string | null | undefined): boolean {
  return role === "owner";
}

/** Line discount: owner, till, and warehouse. Buyer, books, and other roles cannot. */
export function canEditQuoteDiscount(role: string | null | undefined): boolean {
  return role === "owner" || role === "till" || role === "warehouse";
}

/** Ex-VAT line total after a percent discount. The unit price itself is not changed. */
export function quoteLineExVat(
  qty: number | "",
  unitExVat: string,
  discountPercent: string,
): number {
  if (typeof qty !== "number" || qty <= 0) {
    return 0;
  }
  const unit = parsePriceInput(unitExVat);
  if (unit === null || unit <= 0) {
    return 0;
  }
  const parsedDiscount = parsePriceInput(discountPercent) ?? 0;
  const discount = Math.min(100, Math.max(0, parsedDiscount));
  const discountedUnit = roundHalfUp((unit * (100 - discount)) / 100, 2);
  return roundHalfUp(discountedUnit * qty, 2);
}

export type QuoteSkuPrice = {
  unitExVat: number | null;
  source: QuotePriceSource;
  priceListName: string | null;
  warning: string | null;
  pricesIncludeVat: boolean;
};

type QuoteCustomer = Pick<CustomerCrm, "customer_type" | "price_list_id" | "price_classification"> | null;

type QuoteSku = Pick<
  Sku,
  | "id"
  | "our_ref"
  | "name"
  | "our_barcode"
  | "retail_ex_vat"
  | "wholesale_ex_vat"
  | "stockist_ex_vat"
  | "decorator_ex_vat"
>;

const TIER_FIELD = {
  Stockist: "stockist_ex_vat",
  Wholesale: "wholesale_ex_vat",
  Decorator: "decorator_ex_vat",
  Retail: "retail_ex_vat",
} as const;

export function classificationOf(customer: QuoteCustomer): PriceClassification {
  if (customer?.price_classification) {
    return customer.price_classification;
  }
  if (customer?.customer_type === "trade") {
    return "Wholesale";
  }
  return "Retail";
}

/** Retail, and no customer, is the only inclusive display. */
export function pricesIncludeVat(customer: QuoteCustomer): boolean {
  return classificationOf(customer) === "Retail";
}

export function vatBasisLabel(includingVat: boolean): "incl. VAT" | "excl. VAT" {
  return includingVat ? "incl. VAT" : "excl. VAT";
}

export function displayUnitAmount(unitExVat: number, includingVat: boolean): number {
  return includingVat ? exVatToIncVat(unitExVat) : unitExVat;
}

function positiveAmount(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function listUnitExVat(
  sku: Pick<Sku, "id">,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): { unitExVat: number; priceListName: string } | null {
  if (!customer?.price_list_id) {
    return null;
  }
  const list = priceLists.find((entry) => entry.id === customer.price_list_id);
  const item = list?.items.find((row) => row.sku_id === sku.id);
  const unitExVat = positiveAmount(item?.unit_ex_vat);
  if (!list || unitExVat === null) {
    return null;
  }
  return { unitExVat, priceListName: list.name };
}

/**
 * Unit price for a document line, stored ex VAT.
 *
 * Same order as the API: the customer's price list, then the classification
 * tier, then Retail when that tier is missing. No customer → Retail.
 */
export function quoteSkuUnitExVat(
  sku: Pick<Sku, "id" | "retail_ex_vat" | "wholesale_ex_vat" | "stockist_ex_vat" | "decorator_ex_vat">,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): QuoteSkuPrice {
  const classification = classificationOf(customer);
  const includingVat = classification === "Retail";
  const listed = listUnitExVat(sku, customer, priceLists);
  if (listed) {
    return {
      unitExVat: listed.unitExVat,
      source: "price_list",
      priceListName: listed.priceListName,
      warning: null,
      pricesIncludeVat: includingVat,
    };
  }
  const tierField = TIER_FIELD[classification];
  const tierPrice = positiveAmount(sku[tierField]);
  if (tierPrice !== null) {
    return {
      unitExVat: tierPrice,
      source: classification.toLowerCase() as QuotePriceSource,
      priceListName: null,
      warning: null,
      pricesIncludeVat: includingVat,
    };
  }
  const retail = positiveAmount(sku.retail_ex_vat);
  if (classification !== "Retail" && retail !== null) {
    return {
      unitExVat: retail,
      source: "retail_fallback",
      priceListName: null,
      warning: `${classification} price is missing for this SKU; using Retail price`,
      pricesIncludeVat: includingVat,
    };
  }
  if (retail !== null && classification === "Retail") {
    return {
      unitExVat: retail,
      source: "retail",
      priceListName: null,
      warning: null,
      pricesIncludeVat: true,
    };
  }
  return {
    unitExVat: null,
    source: "missing",
    priceListName: null,
    warning: null,
    pricesIncludeVat: includingVat,
  };
}

export function formatUnitExVatInput(unitExVat: number | null): string {
  return unitExVat === null ? "" : formatPriceAmount(unitExVat);
}

/** Dropdown label: code, name, and the price the customer would be charged. */
export function formatQuoteSkuOption(
  sku: QuoteSku,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): string {
  const priced = quoteSkuUnitExVat(sku, customer, priceLists);
  const head = `${sku.our_ref} — ${sku.name}`;
  const basis = vatBasisLabel(priced.pricesIncludeVat);
  if (priced.source === "price_list" && priced.unitExVat !== null) {
    const list = `R ${formatPriceAmount(displayUnitAmount(priced.unitExVat, priced.pricesIncludeVat))}`;
    return `${head} · ${list} list ${basis}`;
  }
  if (priced.unitExVat !== null && priced.source !== "missing") {
    const shown = `R ${formatPriceAmount(displayUnitAmount(priced.unitExVat, priced.pricesIncludeVat))}`;
    const tier =
      priced.source === "retail_fallback" ? "Retail fallback" : classificationOf(customer);
    return `${head} · ${shown} ${tier} ${basis}`;
  }
  return `${head} · no price`;
}

export function quoteSkuMatchesQuery(sku: QuoteSku, inputValue: string | null, label: string): boolean {
  const query = (inputValue ?? "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  const option = label.toLowerCase();
  if (option === query || option.includes(query)) {
    return true;
  }
  return (
    sku.name.toLowerCase().includes(query) ||
    sku.our_ref.toLowerCase().includes(query) ||
    sku.our_barcode.toLowerCase().includes(query)
  );
}

export function quoteUnitPriceHelper(priced: QuoteSkuPrice, hasCustomer: boolean): string {
  const basis = vatBasisLabel(priced.pricesIncludeVat);
  if (priced.warning) {
    return priced.warning;
  }
  if (priced.source === "price_list" && priced.priceListName) {
    return `Price list ${priced.priceListName} overrides the classification · ${basis}`;
  }
  if (priced.source === "stockist") {
    return `Stockist · ${basis}`;
  }
  if (priced.source === "wholesale") {
    return `Wholesale · ${basis}`;
  }
  if (priced.source === "decorator") {
    return `Decorator · ${basis}`;
  }
  if (priced.source === "retail") {
    return hasCustomer ? `Retail · ${basis}` : `Retail · ${basis} (no customer)`;
  }
  return "No catalogue price · enter unit ex VAT";
}
