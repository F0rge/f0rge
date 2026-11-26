import { formatCustomerPrice, isZarCurrency } from "@/lib/order-money";

/** How a piece is sold: in multiples of `multiple`, at least `minimum` per order. */
export type SellRules = { multiple: number; minimum: number };

/** A positive integer, or 1 for anything else (absent, zero, fractional, text). */
export function sellCount(value: unknown): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 1 ? value : 1;
}

/** Reads variant metadata `sell_multiple` / `min_quantity`; the minimum is raised onto the multiple. */
export function sellRules(metadata?: { sell_multiple?: unknown; min_quantity?: unknown } | null): SellRules {
  const multiple = sellCount(metadata?.sell_multiple);
  return { multiple, minimum: Math.ceil(sellCount(metadata?.min_quantity) / multiple) * multiple };
}

/** The most of `available` that is a whole number of multiples. */
export function roundDownToMultiple(available: number, multiple: number): number {
  return Math.max(0, Math.floor(available / multiple) * multiple);
}

/**
 * The quiet price line that makes a batch plain, e.g.
 * "R 2 450,00 each · sold in pairs · R 4 900,00 per pair". Null for a piece sold singly
 * or a price that is not in rand.
 */
export function batchPriceLine(unit: number, currency: string | null | undefined, { multiple, minimum }: SellRules): string | null {
  if ((multiple === 1 && minimum === 1) || !isZarCurrency(currency)) return null;
  const price = (quantity: number) => formatCustomerPrice(unit * quantity, currency);
  const parts = [`${price(1)} each`];
  if (multiple > 1) parts.push(multiple === 2 ? "sold in pairs" : `sold in sets of ${multiple}`);
  if (minimum > multiple) parts.push(`minimum ${minimum}`, `from ${price(minimum)}`);
  else parts.push(`${price(multiple)} per ${multiple === 2 ? "pair" : "set"}`);
  return parts.join(" · ");
}
