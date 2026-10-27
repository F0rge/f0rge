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
  /** The chosen catalogue or list price is strictly under average cost. */
  belowAverageCost: boolean;
};

/**
 * Ex-VAT unit at or under R1.00. That is R1.15 incl. VAT: a Cin7 placeholder of
 * R1.00 ex, or R1.00 incl. VAT stored as R0.87 ex, is caught. R1.01 ex is not.
 */
export const PLACEHOLDER_UNIT_EX_VAT = 1;

export const RESTRICTED_SUSPECT_PRICE_WARNING =
  "Price looks wrong (R1 or below cost) – check with the owner";

export function suspectUnitPriceWarning(input: {
  unitExVat: number | null;
  averageUnitCostZar: string | number | null;
  catalogueBelowCost: boolean;
  unitMatchesCatalogue: boolean;
  canViewCost: boolean;
}): string | null {
  if (input.unitExVat === null || !Number.isFinite(input.unitExVat)) {
    return null;
  }
  const unit = roundHalfUp(input.unitExVat, 2);
  const placeholder = unit <= PLACEHOLDER_UNIT_EX_VAT;
  let belowCost = false;
  let cost: number | null = null;
  if (input.canViewCost && input.averageUnitCostZar != null && input.averageUnitCostZar !== "") {
    const parsed = Number(input.averageUnitCostZar);
    if (Number.isFinite(parsed)) {
      cost = roundHalfUp(parsed, 2);
      belowCost = unit < cost;
    }
  } else if (!input.canViewCost && input.unitMatchesCatalogue && input.catalogueBelowCost) {
    belowCost = true;
  }
  if (!placeholder && !belowCost) {
    return null;
  }
  if (!input.canViewCost) {
    return RESTRICTED_SUSPECT_PRICE_WARNING;
  }
  const shown = formatPriceAmount(unit);
  if (placeholder && belowCost && cost !== null) {
    return `Unit price R${shown} is R1.00 or below and below average cost R${formatPriceAmount(cost)}.`;
  }
  if (belowCost && cost !== null) {
    return `Unit price R${shown} is below average cost R${formatPriceAmount(cost)}.`;
  }
  return "Unit price is R1.00 or below (R1.15 incl. VAT or less). Check this price.";
}

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

const CIN7_NAMED_PRICE_LISTS = new Set([
  "Cin7 Stockist",
  "Cin7 Wholesale",
  "Cin7 Decorator",
  "Cin7 Retail",
]);

/** Cin7 import lists. They must not replace the customer's classification price. */
export function isCin7GeneratedPriceList(name: string | null | undefined): boolean {
  const text = name?.trim() ?? "";
  return CIN7_NAMED_PRICE_LISTS.has(text) || /^Cin7 Tier [1-9]\d*$/.test(text);
}

function listUnitExVat(
  sku: Pick<Sku, "id">,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): { unitExVat: number; priceListName: string; belowAverageCost: boolean } | null {
  if (!customer?.price_list_id) {
    return null;
  }
  const list = priceLists.find((entry) => entry.id === customer.price_list_id);
  if (!list || isCin7GeneratedPriceList(list.name)) {
    return null;
  }
  const item = list.items.find((row) => row.sku_id === sku.id);
  const unitExVat = positiveAmount(item?.unit_ex_vat);
  if (unitExVat === null) {
    return null;
  }
  return {
    unitExVat,
    priceListName: list.name,
    belowAverageCost: item?.below_average_cost === true,
  };
}

function tierBelowAverageCost(
  sku: Pick<Sku, "stockist_below_cost" | "wholesale_below_cost" | "decorator_below_cost" | "retail_below_cost">,
  classification: PriceClassification,
): boolean {
  if (classification === "Stockist") {
    return sku.stockist_below_cost === true;
  }
  if (classification === "Wholesale") {
    return sku.wholesale_below_cost === true;
  }
  if (classification === "Decorator") {
    return sku.decorator_below_cost === true;
  }
  return sku.retail_below_cost === true;
}

/**
 * Unit price for a document line, stored ex VAT.
 *
 * Same order as the API: a hand-made price list, then the classification
 * tier, then Retail when that tier is missing. Cin7 lists are skipped.
 * No customer → Retail.
 */
export function quoteSkuUnitExVat(
  sku: Pick<
    Sku,
    | "id"
    | "retail_ex_vat"
    | "wholesale_ex_vat"
    | "stockist_ex_vat"
    | "decorator_ex_vat"
    | "stockist_below_cost"
    | "wholesale_below_cost"
    | "decorator_below_cost"
    | "retail_below_cost"
  >,
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
      belowAverageCost: listed.belowAverageCost,
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
      belowAverageCost: tierBelowAverageCost(sku, classification),
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
      belowAverageCost: sku.retail_below_cost === true,
    };
  }
  if (retail !== null && classification === "Retail") {
    return {
      unitExVat: retail,
      source: "retail",
      priceListName: null,
      warning: null,
      pricesIncludeVat: true,
      belowAverageCost: sku.retail_below_cost === true,
    };
  }
  return {
    unitExVat: null,
    source: "missing",
    priceListName: null,
    warning: null,
    pricesIncludeVat: includingVat,
    belowAverageCost: false,
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

/** Warning for the unit on a quote or till line. Does not look at the line discount. */
export function quoteLineSuspectWarning(
  unitExVatText: string,
  sku: Pick<Sku, "average_unit_cost_zar"> | null | undefined,
  priced: QuoteSkuPrice | null,
  canViewCost: boolean,
): string | null {
  const unit = parsePriceInput(unitExVatText);
  const catalogue = priced?.unitExVat ?? null;
  const matches =
    unit !== null && catalogue !== null && roundHalfUp(unit, 2) === roundHalfUp(catalogue, 2);
  return suspectUnitPriceWarning({
    unitExVat: unit,
    averageUnitCostZar: canViewCost ? (sku?.average_unit_cost_zar ?? null) : null,
    catalogueBelowCost: priced?.belowAverageCost ?? false,
    unitMatchesCatalogue: matches,
    canViewCost,
  });
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
