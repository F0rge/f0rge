import { ApiError, conflictCode, type SaleLinePrice } from "./api";

/**
 * The browser's side of the sale quantity rule (SPEC 5.3): a SKU sold in multiples of
 * `sell_multiple`, never fewer than `min_sell_qty` on one line. The server decides; these
 * helpers only shape the inputs and lay its messages onto the right lines.
 */
export type SellRule = { sell_multiple?: number | null; min_sell_qty?: number | null };

export function sellRule(sku: SellRule): { multiple: number; minimum: number } {
  const multiple = Math.max(1, Math.floor(sku.sell_multiple ?? 1));
  return { multiple, minimum: Math.max(multiple, Math.floor(sku.min_sell_qty ?? 1)) };
}

/** "Sold in multiples of 2, minimum 4"; null when the SKU sells one at a time. */
export function quantityRuleHelper(sku: SellRule): string | null {
  const { multiple, minimum } = sellRule(sku);
  if (multiple > 1) return minimum > multiple ? `Sold in multiples of ${multiple}, minimum ${minimum}` : `Sold in multiples of ${multiple}`;
  return minimum > 1 ? `Minimum quantity ${minimum}` : null;
}

/** The quantity a new line starts at. */
export function startQty(sku: SellRule): number {
  return sellRule(sku).minimum;
}

export function breaksQuantityRule(sku: SellRule, qty: number): boolean {
  const { multiple, minimum } = sellRule(sku);
  return qty < minimum || qty % multiple !== 0;
}

/** The nearest valid quantity at or above `qty`. */
export function snapQty(sku: SellRule, qty: number): number {
  const { multiple, minimum } = sellRule(sku);
  return Math.max(minimum, Math.ceil(qty / multiple) * multiple);
}

/**
 * NumberInput bounds. Everyone steps by the multiple; only a user who may break a batch
 * (`sales.price_override`) can go below the minimum, so the input never stops them typing.
 */
export function quantityInputBounds(sku: SellRule, canOverride: boolean): { min: number; step: number } {
  const { multiple, minimum } = sellRule(sku);
  return { min: canOverride ? 1 : minimum, step: multiple };
}

/** Per SKU id: the refused quantity and the server's message for that line. */
export type QuantityRuleRefusal = { message: string; lines: Record<string, { qty: number; message: string }> };

/** The 409 `sale_quantity_rule` refusal, or null for any other failure. */
export function quantityRuleRefusal(error: unknown): QuantityRuleRefusal | null {
  if (conflictCode(error) !== "sale_quantity_rule" || !(error instanceof ApiError)) return null;
  const detail = error.detail as { message?: unknown; lines?: unknown };
  const lines: QuantityRuleRefusal["lines"] = {};
  for (const line of Array.isArray(detail.lines) ? detail.lines : []) {
    const entry = line as { sku_id?: unknown; qty?: unknown; message?: unknown };
    if (typeof entry.sku_id === "string" && typeof entry.message === "string") {
      lines[entry.sku_id] = { qty: Number(entry.qty), message: entry.message };
    }
  }
  return { message: typeof detail.message === "string" ? detail.message : error.message, lines };
}

export type LineQuantityNotice = { kind: "error" | "info"; message: string };

/**
 * What a line shows about the rule. The current preview wins; a save refusal shows only
 * while the line still has the quantity that was refused.
 */
export function lineQuantityNotice(
  pricing: Pick<SaleLinePrice, "blocked_by" | "quantity_rule"> | undefined,
  refusal: QuantityRuleRefusal | null | undefined,
  skuId: string | null | undefined,
  qty: number,
): LineQuantityNotice | null {
  if (pricing?.quantity_rule) {
    return { kind: pricing.blocked_by === "quantity_rule" ? "error" : "info", message: pricing.quantity_rule };
  }
  const refused = skuId ? refusal?.lines[skuId] : undefined;
  return refused && refused.qty === qty ? { kind: "error", message: refused.message } : null;
}
