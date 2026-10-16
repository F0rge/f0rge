const ZAR = "ZAR";

export function isZarCurrency(currency: string | null | undefined): boolean {
  if (currency == null || currency.trim() === "") return true;
  return currency.trim().toUpperCase() === ZAR;
}

/** Customer-facing rand amount. Never formats another currency. */
export function formatZar(value: number | string | null | undefined): string {
  if (value == null || value === "") return "—";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: ZAR }).format(amount);
}

/**
 * Formats a customer-facing price in ZAR.
 * A non-ZAR currency code is refused so a foreign amount is not relabelled as rand.
 */
export function formatCustomerPrice(value: number | string | null | undefined, currency?: string | null): string {
  if (!isZarCurrency(currency)) return "Price unavailable";
  return formatZar(value);
}

export function orderMoney(value: number | string | null | undefined, currency = ZAR): string {
  return formatCustomerPrice(value, currency);
}
