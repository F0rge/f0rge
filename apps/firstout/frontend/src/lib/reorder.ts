import type { ReorderRow } from "./api";

type Suggestion = Pick<ReorderRow, "need_qty" | "suggested_qty" | "min_order_qty" | "pack_multiple">;

/**
 * Why a reorder suggestion differs from the need: "Needs 7, rounded to 12 (minimum order 12,
 * packs of 2)". Null when the suggestion is the need itself. The server does the rounding.
 */
export function reorderExplanation(row: Suggestion): string | null {
  if (Number(row.suggested_qty) === Number(row.need_qty)) return null;
  const reasons = [
    row.min_order_qty && row.min_order_qty > 1 ? `minimum order ${row.min_order_qty}` : null,
    row.pack_multiple && row.pack_multiple > 1 ? `packs of ${row.pack_multiple}` : null,
  ].filter(Boolean);
  const why = reasons.length ? ` (${reasons.join(", ")})` : "";
  return `Needs ${row.need_qty}, rounded to ${row.suggested_qty}${why}`;
}
