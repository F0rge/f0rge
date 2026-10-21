import {
  formatPriceAmount,
  parsePriceInput,
  roundHalfUp,
  type CustomerCrm,
  type PriceList,
  type Sku,
} from "@/lib/api";

/** How a quote line's starting unit price was chosen. All amounts are ex VAT. */
export type QuotePriceSource = "price_list" | "wholesale" | "retail" | "missing";

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
};

type QuoteCustomer = Pick<CustomerCrm, "customer_type" | "price_list_id"> | null;

type QuoteSku = Pick<Sku, "id" | "our_ref" | "name" | "our_barcode" | "retail_ex_vat" | "wholesale_ex_vat">;

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

function moneyLabel(value: string | null | undefined): string {
  const amount = positiveAmount(value);
  return amount === null ? "—" : `R ${formatPriceAmount(amount)}`;
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
 * Unit price for a quote line, ex VAT.
 *
 * Same order as the API (`resolve_unit_ex_vat`): the customer's price list,
 * then wholesale ex VAT for a trade customer, otherwise retail ex VAT.
 * `customers.price_tier` is a label and is not used. No customer → retail.
 */
export function quoteSkuUnitExVat(
  sku: Pick<Sku, "id" | "retail_ex_vat" | "wholesale_ex_vat">,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): QuoteSkuPrice {
  const listed = listUnitExVat(sku, customer, priceLists);
  if (listed) {
    return {
      unitExVat: listed.unitExVat,
      source: "price_list",
      priceListName: listed.priceListName,
    };
  }
  const wholesale = positiveAmount(sku.wholesale_ex_vat);
  if (customer?.customer_type === "trade" && wholesale !== null) {
    return { unitExVat: wholesale, source: "wholesale", priceListName: null };
  }
  const retail = positiveAmount(sku.retail_ex_vat);
  if (retail !== null) {
    return { unitExVat: retail, source: "retail", priceListName: null };
  }
  return { unitExVat: null, source: "missing", priceListName: null };
}

export function formatUnitExVatInput(unitExVat: number | null): string {
  return unitExVat === null ? "" : formatPriceAmount(unitExVat);
}

/** Dropdown label: code, name, and ex-VAT retail plus wholesale (list price when it applies). */
export function formatQuoteSkuOption(
  sku: QuoteSku,
  customer: QuoteCustomer,
  priceLists: PriceList[],
): string {
  const priced = quoteSkuUnitExVat(sku, customer, priceLists);
  const retail = moneyLabel(sku.retail_ex_vat);
  const wholesale = moneyLabel(sku.wholesale_ex_vat);
  const head = `${sku.our_ref} — ${sku.name}`;
  if (priced.source === "price_list" && priced.unitExVat !== null) {
    const list = `R ${formatPriceAmount(priced.unitExVat)}`;
    return `${head} · ${list} list ex VAT · retail ${retail} · wholesale ${wholesale}`;
  }
  if (priced.source === "wholesale") {
    return `${head} · ${wholesale} wholesale ex VAT · retail ${retail}`;
  }
  if (priced.source === "retail") {
    return `${head} · ${retail} retail ex VAT · wholesale ${wholesale}`;
  }
  return `${head} · no ex VAT price · retail ${retail} · wholesale ${wholesale}`;
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
  if (priced.source === "price_list" && priced.priceListName) {
    return `Price list ${priced.priceListName} · ex VAT`;
  }
  if (priced.source === "wholesale") {
    return "Trade wholesale · ex VAT";
  }
  if (priced.source === "retail") {
    return hasCustomer ? "Retail · ex VAT" : "Retail · ex VAT (no customer)";
  }
  return "No catalogue price · enter unit ex VAT";
}
